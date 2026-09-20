from __future__ import annotations

import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .recipes import RECIPE_CONTRACT_VERSION, canonicalize_recipe
from .inference import vision_record_from_photo


LEARNING_SAMPLE_FORMAT = "prographer-production-learning-sample-v1"
LEARNING_VERDICTS = {"approved", "corrected"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_learning_schema(conn: sqlite3.Connection) -> None:
    """
    Additive / idempotent Stage 5 migration.

    The new learning store is intentionally separate from the legacy `feedback`
    and Style DNA tables, so canonical Kelvin / Lightroom Legacy values can never
    be mixed into the old -100..100 feedback pipeline.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ai_learning_samples (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            registry_id TEXT NOT NULL,
            profile_version_id TEXT NOT NULL,
            profile_version_number INTEGER NOT NULL,

            prediction_id TEXT,
            source_photo_id TEXT,
            source_event_id TEXT,
            brain_analysis_id TEXT,

            verdict TEXT NOT NULL,
            recipe_contract_version TEXT NOT NULL,
            process_family TEXT NOT NULL DEFAULT 'unknown',

            ai_recipe_json TEXT NOT NULL,
            photographer_recipe_json TEXT NOT NULL,
            delta_json TEXT NOT NULL,
            feature_record_json TEXT NOT NULL,

            note TEXT NOT NULL DEFAULT '',
            final_render_path TEXT,

            is_current INTEGER NOT NULL DEFAULT 1,
            supersedes_sample_id TEXT,

            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(registry_id) REFERENCES ai_profile_registries(id) ON DELETE CASCADE,
            FOREIGN KEY(profile_version_id) REFERENCES ai_profile_versions(id) ON DELETE CASCADE,
            FOREIGN KEY(prediction_id) REFERENCES photo_ai_predictions(id) ON DELETE SET NULL,
            FOREIGN KEY(source_photo_id) REFERENCES photos(id) ON DELETE SET NULL,
            FOREIGN KEY(source_event_id) REFERENCES events(id) ON DELETE SET NULL,
            FOREIGN KEY(brain_analysis_id) REFERENCES photo_brain_vision(id) ON DELETE SET NULL,
            FOREIGN KEY(supersedes_sample_id) REFERENCES ai_learning_samples(id) ON DELETE SET NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_learning_one_current_prediction
            ON ai_learning_samples(prediction_id)
            WHERE prediction_id IS NOT NULL AND is_current = 1;

        CREATE INDEX IF NOT EXISTS idx_ai_learning_user_current
            ON ai_learning_samples(user_id, is_current, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_ai_learning_profile_version
            ON ai_learning_samples(profile_version_id, is_current, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_ai_learning_source_photo
            ON ai_learning_samples(source_photo_id, created_at DESC);
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


def _round_delta(value: float) -> float:
    if abs(value) < 0.0000001:
        return 0.0
    return round(float(value), 4)


def merged_final_recipe(
    ai_recipe: dict[str, Any],
    photographer_recipe: Optional[dict[str, Any]],
    *,
    verdict: str,
) -> dict[str, float]:
    ai = canonicalize_recipe(ai_recipe or {})
    if not ai:
        raise RuntimeError("AI prediction contains no canonical recipe.")

    if verdict == "approved":
        return dict(ai)

    if verdict != "corrected":
        raise RuntimeError(f"Unsupported learning verdict: {verdict}")

    supplied = canonicalize_recipe(photographer_recipe or {})
    if not supplied:
        raise RuntimeError("A corrected decision requires a photographer recipe.")

    # The photographer recipe is a FINAL recipe.  Still, merge missing keys from
    # AI defensively so a partial client payload cannot accidentally erase controls.
    final = dict(ai)
    final.update(supplied)
    return canonicalize_recipe(final)


def recipe_delta(
    ai_recipe: dict[str, Any],
    photographer_recipe: dict[str, Any],
) -> dict[str, float]:
    ai = canonicalize_recipe(ai_recipe or {})
    final = canonicalize_recipe(photographer_recipe or {})
    keys = sorted(set(ai) | set(final))

    delta: dict[str, float] = {}
    for key in keys:
        if key not in ai or key not in final:
            continue
        delta[key] = _round_delta(float(final[key]) - float(ai[key]))
    return delta


def changed_parameters(delta: dict[str, Any]) -> list[str]:
    return [
        key
        for key, value in delta.items()
        if abs(float(value or 0.0)) > 0.0001
    ]


def _sample_public(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["is_current"] = bool(item.get("is_current"))
    item["ai_recipe"] = _safe_json(item.pop("ai_recipe_json", "{}"), {})
    item["photographer_recipe"] = _safe_json(
        item.pop("photographer_recipe_json", "{}"),
        {},
    )
    item["delta"] = _safe_json(item.pop("delta_json", "{}"), {})
    item["feature_record"] = _safe_json(item.pop("feature_record_json", "{}"), {})
    item["changed_parameters"] = changed_parameters(item["delta"])
    item["changed_parameter_count"] = len(item["changed_parameters"])
    return item


def latest_learning_for_prediction(
    conn: sqlite3.Connection,
    *,
    prediction_id: str,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT *
        FROM ai_learning_samples
        WHERE prediction_id=? AND is_current=1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (prediction_id,),
    ).fetchone()
    return _sample_public(row) if row else None


def latest_learning_for_photo(
    conn: sqlite3.Connection,
    *,
    photo_id: str,
    profile_version_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if profile_version_id:
        row = conn.execute(
            """
            SELECT *
            FROM ai_learning_samples
            WHERE source_photo_id=?
              AND profile_version_id=?
              AND is_current=1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (photo_id, profile_version_id),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT *
            FROM ai_learning_samples
            WHERE source_photo_id=?
              AND is_current=1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (photo_id,),
        ).fetchone()
    return _sample_public(row) if row else None


def save_learning_decision(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    photo_row: sqlite3.Row | dict[str, Any],
    brain_row: sqlite3.Row | dict[str, Any],
    prediction: dict[str, Any],
    verdict: str,
    photographer_recipe: Optional[dict[str, Any]],
    process_family: str,
    note: str = "",
    final_render_path: Optional[str] = None,
) -> dict[str, Any]:
    if verdict not in LEARNING_VERDICTS:
        raise RuntimeError("Learning verdict must be approved or corrected.")

    photo = dict(photo_row)
    brain = dict(brain_row)

    ai_recipe = canonicalize_recipe(prediction.get("recipe") or {})
    final_recipe = merged_final_recipe(
        ai_recipe,
        photographer_recipe,
        verdict=verdict,
    )
    delta = recipe_delta(ai_recipe, final_recipe)

    # Snapshot the exact model input now.  This makes the learning sample
    # self-contained and usable for Stage 6 even if the user later deletes the
    # source event and the photo/brain/prediction rows disappear.
    feature_record = vision_record_from_photo(photo, brain)

    # A photo may be re-inferred after a newer Profile becomes ACTIVE.  The
    # photographer still has exactly one FINAL decision for that photo.
    current = conn.execute(
        """
        SELECT *
        FROM ai_learning_samples
        WHERE source_photo_id=? AND is_current=1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (photo["id"],),
    ).fetchone()

    supersedes_id = str(current["id"]) if current else None
    now = _utc_now()

    conn.execute(
        """
        UPDATE ai_learning_samples
        SET is_current=0, updated_at=?
        WHERE source_photo_id=? AND is_current=1
        """,
        (now, photo["id"]),
    )

    sample_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO ai_learning_samples (
            id,user_id,registry_id,profile_version_id,profile_version_number,
            prediction_id,source_photo_id,source_event_id,brain_analysis_id,
            verdict,recipe_contract_version,process_family,
            ai_recipe_json,photographer_recipe_json,delta_json,feature_record_json,
            note,final_render_path,is_current,supersedes_sample_id,
            created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            sample_id,
            user_id,
            prediction["registry_id"],
            prediction["profile_version_id"],
            int(prediction["profile_version_number"]),
            prediction["id"],
            photo["id"],
            photo["event_id"],
            brain["id"],
            verdict,
            prediction.get("recipe_contract_version") or RECIPE_CONTRACT_VERSION,
            str(process_family or "unknown"),
            json.dumps(ai_recipe, ensure_ascii=False),
            json.dumps(final_recipe, ensure_ascii=False),
            json.dumps(delta, ensure_ascii=False),
            json.dumps(feature_record, ensure_ascii=False),
            str(note or ""),
            final_render_path,
            1,
            supersedes_id,
            now,
            now,
        ),
    )

    row = conn.execute(
        "SELECT * FROM ai_learning_samples WHERE id=?",
        (sample_id,),
    ).fetchone()
    return _sample_public(row)


def set_learning_final_render(
    conn: sqlite3.Connection,
    *,
    sample_id: str,
    final_render_path: Optional[str],
) -> dict[str, Any]:
    conn.execute(
        """
        UPDATE ai_learning_samples
        SET final_render_path=?, updated_at=?
        WHERE id=?
        """,
        (final_render_path, _utc_now(), sample_id),
    )
    row = conn.execute(
        "SELECT * FROM ai_learning_samples WHERE id=?",
        (sample_id,),
    ).fetchone()
    if not row:
        raise RuntimeError("Learning sample not found.")
    return _sample_public(row)


def learning_summary(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    profile_version_id: Optional[str] = None,
) -> dict[str, Any]:
    where = ["user_id=?", "is_current=1"]
    params: list[Any] = [user_id]
    if profile_version_id:
        where.append("profile_version_id=?")
        params.append(profile_version_id)

    rows = conn.execute(
        f"""
        SELECT verdict, delta_json, profile_version_id, profile_version_number
        FROM ai_learning_samples
        WHERE {' AND '.join(where)}
        ORDER BY created_at ASC
        """,
        tuple(params),
    ).fetchall()

    approved = 0
    corrected = 0
    target_changes: dict[str, list[float]] = {}

    for row in rows:
        verdict = str(row["verdict"] or "")
        if verdict == "approved":
            approved += 1
        elif verdict == "corrected":
            corrected += 1

        delta = _safe_json(row["delta_json"], {})
        for key, raw_value in delta.items():
            try:
                value = float(raw_value)
            except Exception:
                continue
            if not math.isfinite(value) or abs(value) <= 0.0001:
                continue
            target_changes.setdefault(key, []).append(value)

    total = approved + corrected
    acceptance_rate = round((approved / total) * 100.0, 1) if total else None

    target_summary = {}
    for key, values in target_changes.items():
        target_summary[key] = {
            "correction_count": len(values),
            "mean_delta": round(sum(values) / len(values), 4),
            "mean_absolute_delta": round(
                sum(abs(v) for v in values) / len(values),
                4,
            ),
        }

    return {
        "format": LEARNING_SAMPLE_FORMAT,
        "sample_count": total,
        "approved_count": approved,
        "corrected_count": corrected,
        "acceptance_rate": acceptance_rate,
        "target_corrections": target_summary,
        "ready_for_retraining": total > 0,
    }
