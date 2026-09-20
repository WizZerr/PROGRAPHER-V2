from __future__ import annotations

import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .production_profile import predict_production_recipe
from .profile_registry import resolve_data_path


INFERENCE_FORMAT = "prographer-active-profile-inference-v1"
VISION_PREPROCESSING_CONTRACT = "prographer-training-vision-v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_inference_schema(conn: sqlite3.Connection) -> None:
    """
    Additive, idempotent Stage 3 migration.
    No existing rows/tables are cleared or rewritten.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS photo_ai_predictions (
            id TEXT PRIMARY KEY,
            photo_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            registry_id TEXT NOT NULL,
            profile_version_id TEXT NOT NULL,
            profile_version_number INTEGER NOT NULL,
            brain_analysis_id TEXT NOT NULL,
            profile_format TEXT NOT NULL,
            recipe_contract_version TEXT NOT NULL,
            recipe_json TEXT NOT NULL,
            provenance_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            UNIQUE(photo_id, profile_version_id, brain_analysis_id),
            FOREIGN KEY(photo_id) REFERENCES photos(id) ON DELETE CASCADE,
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(registry_id) REFERENCES ai_profile_registries(id) ON DELETE CASCADE,
            FOREIGN KEY(profile_version_id) REFERENCES ai_profile_versions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_photo_ai_predictions_photo
            ON photo_ai_predictions(photo_id, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_photo_ai_predictions_event_version
            ON photo_ai_predictions(event_id, profile_version_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS event_ai_inference_jobs (
            id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            registry_id TEXT NOT NULL,
            profile_version_id TEXT NOT NULL,
            profile_version_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            stage TEXT NOT NULL DEFAULT 'queued',
            progress_percent INTEGER NOT NULL DEFAULT 0,
            total_photos INTEGER NOT NULL DEFAULT 0,
            processed_photos INTEGER NOT NULL DEFAULT 0,
            predicted_photos INTEGER NOT NULL DEFAULT 0,
            reused_photos INTEGER NOT NULL DEFAULT 0,
            failed_photos INTEGER NOT NULL DEFAULT 0,
            details_json TEXT NOT NULL DEFAULT '{}',
            error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(registry_id) REFERENCES ai_profile_registries(id) ON DELETE CASCADE,
            FOREIGN KEY(profile_version_id) REFERENCES ai_profile_versions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_event_ai_inference_jobs_event
            ON event_ai_inference_jobs(event_id, created_at DESC);
        """
    )


def _safe_json(value: Any, fallback):
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return fallback


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip().lower().replace(",", "")
        text = text.replace("mm", "").replace("sec", "").strip()
        if text.startswith("f/"):
            text = text[2:]
        if "/" in text:
            left, right = text.split("/", 1)
            left = left.strip()
            right = right.strip()
            if left.replace(".", "", 1).isdigit() and right.replace(".", "", 1).isdigit():
                denominator = float(right)
                return float(left) / denominator if denominator else default
        result = float(text)
        return result if math.isfinite(result) else default
    except Exception:
        return default


def normalized_feature_metadata(
    photo_row: sqlite3.Row | dict[str, Any],
    semantics: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    photo = dict(photo_row)
    semantic_payload = semantics or {}

    # Stage 3 brain rows save the exact training-contract metadata here.
    embedded = semantic_payload.get("feature_metadata")
    if isinstance(embedded, dict) and embedded:
        metadata = dict(embedded)
    else:
        metadata = _safe_json(photo.get("metadata_json"), {})

    width = _safe_float(metadata.get("width"), _safe_float(photo.get("width"), 0.0))
    height = _safe_float(metadata.get("height"), _safe_float(photo.get("height"), 0.0))

    return {
        "iso": _safe_float(metadata.get("iso"), 0.0),
        "aperture": _safe_float(metadata.get("aperture"), 0.0),
        "shutter_seconds": _safe_float(
            metadata.get("shutter_seconds", metadata.get("shutter_speed")),
            0.0,
        ),
        "focal_length": _safe_float(metadata.get("focal_length"), 0.0),
        "width": width,
        "height": height,
        "camera_make": str(metadata.get("camera_make") or ""),
        "camera_model": str(metadata.get("camera_model") or ""),
        "lens": str(metadata.get("lens") or ""),
    }


def vision_record_from_photo(
    photo_row: sqlite3.Row | dict[str, Any],
    brain_row: sqlite3.Row | dict[str, Any],
) -> dict[str, Any]:
    photo = dict(photo_row)
    brain = dict(brain_row)
    semantics_payload = _safe_json(brain.get("semantics_json"), {})
    embedding = _safe_json(brain.get("embedding_json"), [])

    if not isinstance(embedding, list) or not embedding:
        raise RuntimeError("Vision embedding is missing for this photo.")

    return {
        "sample_id": photo.get("id"),
        "filename": photo.get("original_name"),
        "metadata": normalized_feature_metadata(photo, semantics_payload),
        "embedding": embedding,
        "semantics": {
            "groups": semantics_payload.get("groups") or {},
            "top": semantics_payload.get("top") or {},
        },
        "vision_model": brain.get("model_name"),
        "vision_device": brain.get("device"),
    }


def brain_matches_production_contract(brain_row: sqlite3.Row | dict[str, Any]) -> bool:
    brain = dict(brain_row)
    semantics = _safe_json(brain.get("semantics_json"), {})
    return semantics.get("preprocessing_contract") == VISION_PREPROCESSING_CONTRACT


def _prediction_public(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["recipe"] = _safe_json(item.pop("recipe_json", "{}"), {})
    item["provenance"] = _safe_json(item.pop("provenance_json", "{}"), {})
    return item


def latest_prediction_for_photo(
    conn: sqlite3.Connection,
    *,
    photo_id: str,
    profile_version_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if profile_version_id:
        row = conn.execute(
            """
            SELECT *
            FROM photo_ai_predictions
            WHERE photo_id=? AND profile_version_id=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (photo_id, profile_version_id),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT *
            FROM photo_ai_predictions
            WHERE photo_id=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (photo_id,),
        ).fetchone()

    return _prediction_public(row) if row else None


def current_prediction_map(
    conn: sqlite3.Connection,
    *,
    photo_ids: list[str],
    profile_version_id: str,
) -> dict[str, dict[str, Any]]:
    if not photo_ids:
        return {}

    placeholders = ",".join("?" for _ in photo_ids)
    rows = conn.execute(
        f"""
        SELECT *
        FROM photo_ai_predictions
        WHERE profile_version_id=?
          AND photo_id IN ({placeholders})
        ORDER BY created_at DESC
        """,
        (profile_version_id, *photo_ids),
    ).fetchall()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = _prediction_public(row)
        if item["photo_id"] not in result:
            result[item["photo_id"]] = item
    return result


def predict_photo_with_active_registry(
    conn: sqlite3.Connection,
    *,
    data_dir: Path,
    user_id: str,
    photo_row: sqlite3.Row | dict[str, Any],
    brain_row: sqlite3.Row | dict[str, Any],
    active_registry: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    photo = dict(photo_row)
    brain = dict(brain_row)

    active_version = active_registry.get("active_version")
    if not active_version:
        raise RuntimeError("AI Profile has no ACTIVE version.")

    version_id = str(active_version["id"])
    existing = conn.execute(
        """
        SELECT *
        FROM photo_ai_predictions
        WHERE photo_id=? AND profile_version_id=? AND brain_analysis_id=?
        LIMIT 1
        """,
        (photo["id"], version_id, brain["id"]),
    ).fetchone()
    if existing:
        return _prediction_public(existing), True

    artifact_path = resolve_data_path(Path(data_dir), str(active_version["artifact_path"]))
    if not artifact_path.exists():
        raise RuntimeError(f"ACTIVE AI Profile artifact is missing: {artifact_path}")

    vision_record = vision_record_from_photo(photo, brain)
    prediction = predict_production_recipe(artifact_path, vision_record)
    recipe = prediction.get("recipe") or {}
    recipe_contract_version = str(prediction.get("recipe_contract_version") or "")
    profile_format = str(prediction.get("profile_format") or "")

    if not recipe:
        raise RuntimeError("ACTIVE AI Profile returned an empty recipe.")
    if not recipe_contract_version:
        raise RuntimeError("ACTIVE AI Profile returned no recipe contract version.")

    prediction_id = str(uuid.uuid4())
    created_at = _utc_now()
    provenance = {
        "inference_format": INFERENCE_FORMAT,
        "registry_id": active_registry["id"],
        "registry_name": active_registry.get("name"),
        "profile_version_id": version_id,
        "profile_version_number": int(active_version["version_number"]),
        "brain_analysis_id": brain["id"],
        "vision_model": brain.get("model_name"),
        "vision_device": brain.get("device"),
        "vision_preprocessing_contract": (
            _safe_json(brain.get("semantics_json"), {}).get("preprocessing_contract")
        ),
        "process_family": prediction.get("process_family") or "unknown",
    }

    conn.execute(
        """
        INSERT INTO photo_ai_predictions (
            id,photo_id,event_id,user_id,registry_id,profile_version_id,
            profile_version_number,brain_analysis_id,profile_format,
            recipe_contract_version,recipe_json,provenance_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            prediction_id,
            photo["id"],
            photo["event_id"],
            user_id,
            active_registry["id"],
            version_id,
            int(active_version["version_number"]),
            brain["id"],
            profile_format,
            recipe_contract_version,
            json.dumps(recipe, ensure_ascii=False),
            json.dumps(provenance, ensure_ascii=False),
            created_at,
        ),
    )

    row = conn.execute(
        "SELECT * FROM photo_ai_predictions WHERE id=?",
        (prediction_id,),
    ).fetchone()
    return _prediction_public(row), False


def event_prediction_coverage(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    profile_version_id: Optional[str],
) -> dict[str, Any]:
    total = int(
        conn.execute(
            "SELECT COUNT(*) c FROM photos WHERE event_id=?",
            (event_id,),
        ).fetchone()["c"]
    )
    eligible = int(
        conn.execute(
            """
            SELECT COUNT(*) c
            FROM photos
            WHERE event_id=? AND original_path IS NOT NULL AND original_path <> ''
            """,
            (event_id,),
        ).fetchone()["c"]
    )

    predicted = 0
    if profile_version_id:
        predicted = int(
            conn.execute(
                """
                SELECT COUNT(DISTINCT photo_id) c
                FROM photo_ai_predictions
                WHERE event_id=? AND profile_version_id=?
                """,
                (event_id, profile_version_id),
            ).fetchone()["c"]
        )

    denominator = max(1, eligible)
    return {
        "total_photos": total,
        "eligible_photos": eligible,
        "predicted_photos": predicted,
        "missing_photos": max(0, eligible - predicted),
        "progress_percent": round(predicted / denominator * 100.0, 1) if eligible else 0.0,
        "complete": bool(eligible and predicted >= eligible),
    }


def create_event_inference_job(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    user_id: str,
    active_registry: dict[str, Any],
    total_photos: int,
) -> dict[str, Any]:
    active_version = active_registry["active_version"]
    job_id = str(uuid.uuid4())
    now = _utc_now()

    conn.execute(
        """
        INSERT INTO event_ai_inference_jobs (
            id,event_id,user_id,registry_id,profile_version_id,
            profile_version_number,status,stage,progress_percent,total_photos,
            processed_photos,predicted_photos,reused_photos,failed_photos,
            details_json,error,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            job_id,
            event_id,
            user_id,
            active_registry["id"],
            active_version["id"],
            int(active_version["version_number"]),
            "queued",
            "queued",
            0,
            int(total_photos),
            0,
            0,
            0,
            0,
            json.dumps(
                {
                    "profile_name": active_registry.get("name"),
                    "recipe_contract_version": active_version.get("recipe_contract_version"),
                },
                ensure_ascii=False,
            ),
            "",
            now,
            now,
        ),
    )
    row = conn.execute(
        "SELECT * FROM event_ai_inference_jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    return job_public(row)


def update_event_inference_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    progress_percent: Optional[int] = None,
    processed_photos: Optional[int] = None,
    predicted_photos: Optional[int] = None,
    reused_photos: Optional[int] = None,
    failed_photos: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM event_ai_inference_jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    if not row:
        raise RuntimeError("Inference job not found.")

    current = dict(row)
    conn.execute(
        """
        UPDATE event_ai_inference_jobs
        SET status=?, stage=?, progress_percent=?, processed_photos=?,
            predicted_photos=?, reused_photos=?, failed_photos=?,
            details_json=?, error=?, updated_at=?
        WHERE id=?
        """,
        (
            status if status is not None else current["status"],
            stage if stage is not None else current["stage"],
            int(progress_percent if progress_percent is not None else current["progress_percent"]),
            int(processed_photos if processed_photos is not None else current["processed_photos"]),
            int(predicted_photos if predicted_photos is not None else current["predicted_photos"]),
            int(reused_photos if reused_photos is not None else current["reused_photos"]),
            int(failed_photos if failed_photos is not None else current["failed_photos"]),
            json.dumps(details, ensure_ascii=False)
            if details is not None
            else current["details_json"],
            error if error is not None else current["error"],
            _utc_now(),
            job_id,
        ),
    )
    updated = conn.execute(
        "SELECT * FROM event_ai_inference_jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    return job_public(updated)


def job_public(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["details"] = _safe_json(item.pop("details_json", "{}"), {})
    return item


def latest_event_inference_job(
    conn: sqlite3.Connection,
    *,
    event_id: str,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT *
        FROM event_ai_inference_jobs
        WHERE event_id=?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (event_id,),
    ).fetchone()
    return job_public(row) if row else None


def active_event_inference_job(
    conn: sqlite3.Connection,
    *,
    event_id: str,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT *
        FROM event_ai_inference_jobs
        WHERE event_id=? AND status IN ('queued','running')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (event_id,),
    ).fetchone()
    return job_public(row) if row else None
