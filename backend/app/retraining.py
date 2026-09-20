from __future__ import annotations

import copy
import hashlib
import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .profile_ai import _feature_vector
from .production_profile import predict_production_recipes_from_artifact
from .profile_registry import register_production_profile_snapshot, resolve_data_path
from .recipes import RECIPE_CONTRACT_VERSION, clamp_recipe_value


RETRAINING_FORMAT = "prographer-adaptive-retraining-v1"
ADAPTATION_FORMAT = "prographer-context-residual-adaptation-v1"

MIN_TOTAL_SAMPLES = 20
MIN_VALIDATION_SAMPLES = 4
MIN_TRAIN_SAMPLES_PER_TARGET = 12
MIN_VALIDATION_SAMPLES_PER_TARGET = 4
MIN_NONZERO_SUPPORT_PER_TARGET = 5
MIN_RELATIVE_IMPROVEMENT_PERCENT = 2.0
MIN_NEW_SAMPLES_AFTER_ADAPTATION = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_retraining_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ai_retraining_runs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            registry_id TEXT NOT NULL,
            parent_version_id TEXT NOT NULL,
            parent_version_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            stage TEXT NOT NULL DEFAULT 'queued',
            progress_percent INTEGER NOT NULL DEFAULT 0,

            sample_count INTEGER NOT NULL DEFAULT 0,
            train_count INTEGER NOT NULL DEFAULT 0,
            validation_count INTEGER NOT NULL DEFAULT 0,

            adapted_targets_json TEXT NOT NULL DEFAULT '[]',
            metrics_json TEXT NOT NULL DEFAULT '{}',
            candidate_version_id TEXT,

            error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(registry_id) REFERENCES ai_profile_registries(id) ON DELETE CASCADE,
            FOREIGN KEY(parent_version_id) REFERENCES ai_profile_versions(id) ON DELETE CASCADE,
            FOREIGN KEY(candidate_version_id) REFERENCES ai_profile_versions(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_ai_retraining_user
            ON ai_retraining_runs(user_id, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_ai_retraining_registry
            ON ai_retraining_runs(registry_id, created_at DESC);
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


def retraining_run_public(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["adapted_targets"] = _safe_json(item.pop("adapted_targets_json", "[]"), [])
    item["metrics"] = _safe_json(item.pop("metrics_json", "{}"), {})
    return item


def latest_retraining_run(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    registry_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if registry_id:
        row = conn.execute(
            """
            SELECT *
            FROM ai_retraining_runs
            WHERE user_id=? AND registry_id=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, registry_id),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT *
            FROM ai_retraining_runs
            WHERE user_id=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return retraining_run_public(row) if row else None


def active_retraining_run(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    registry_id: str,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT *
        FROM ai_retraining_runs
        WHERE user_id=? AND registry_id=?
          AND status IN ('queued','running')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id, registry_id),
    ).fetchone()
    return retraining_run_public(row) if row else None


def create_retraining_run(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    registry_id: str,
    parent_version_id: str,
    parent_version_number: int,
    sample_count: int,
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO ai_retraining_runs (
            id,user_id,registry_id,parent_version_id,parent_version_number,
            status,stage,progress_percent,sample_count,train_count,validation_count,
            adapted_targets_json,metrics_json,candidate_version_id,error,
            created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            user_id,
            registry_id,
            parent_version_id,
            int(parent_version_number),
            "queued",
            "queued",
            0,
            int(sample_count),
            0,
            0,
            "[]",
            "{}",
            None,
            "",
            now,
            now,
        ),
    )
    row = conn.execute(
        "SELECT * FROM ai_retraining_runs WHERE id=?",
        (run_id,),
    ).fetchone()
    return retraining_run_public(row)


def update_retraining_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    progress_percent: Optional[int] = None,
    sample_count: Optional[int] = None,
    train_count: Optional[int] = None,
    validation_count: Optional[int] = None,
    adapted_targets: Optional[list[str]] = None,
    metrics: Optional[dict[str, Any]] = None,
    candidate_version_id: Optional[str] = None,
    error: Optional[str] = None,
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM ai_retraining_runs WHERE id=?",
        (run_id,),
    ).fetchone()
    if not row:
        raise RuntimeError("Retraining run not found.")

    current = dict(row)
    conn.execute(
        """
        UPDATE ai_retraining_runs
        SET status=?,stage=?,progress_percent=?,
            sample_count=?,train_count=?,validation_count=?,
            adapted_targets_json=?,metrics_json=?,candidate_version_id=?,
            error=?,updated_at=?
        WHERE id=?
        """,
        (
            status if status is not None else current["status"],
            stage if stage is not None else current["stage"],
            int(progress_percent if progress_percent is not None else current["progress_percent"]),
            int(sample_count if sample_count is not None else current["sample_count"]),
            int(train_count if train_count is not None else current["train_count"]),
            int(validation_count if validation_count is not None else current["validation_count"]),
            json.dumps(adapted_targets, ensure_ascii=False)
            if adapted_targets is not None
            else current["adapted_targets_json"],
            json.dumps(metrics, ensure_ascii=False)
            if metrics is not None
            else current["metrics_json"],
            candidate_version_id
            if candidate_version_id is not None
            else current["candidate_version_id"],
            error if error is not None else current["error"],
            _utc_now(),
            run_id,
        ),
    )
    updated = conn.execute(
        "SELECT * FROM ai_retraining_runs WHERE id=?",
        (run_id,),
    ).fetchone()
    return retraining_run_public(updated)


def _current_learning_rows(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    registry_id: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM ai_learning_samples
        WHERE user_id=? AND registry_id=? AND is_current=1
          AND recipe_contract_version=?
        ORDER BY created_at ASC
        """,
        (user_id, registry_id, RECIPE_CONTRACT_VERSION),
    ).fetchall()

    output = []
    for row in rows:
        item = dict(row)
        item["photographer_recipe"] = _safe_json(
            item.get("photographer_recipe_json"),
            {},
        )
        item["feature_record"] = _safe_json(
            item.get("feature_record_json"),
            {},
        )
        output.append(item)
    return output


def retraining_readiness(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    registry_id: str,
) -> dict[str, Any]:
    rows = _current_learning_rows(
        conn,
        user_id=user_id,
        registry_id=registry_id,
    )
    approved = sum(1 for row in rows if row.get("verdict") == "approved")
    corrected = sum(1 for row in rows if row.get("verdict") == "corrected")
    count = len(rows)

    active = conn.execute(
        """
        SELECT version_number,activated_at,created_at,summary_json
        FROM ai_profile_versions
        WHERE registry_id=? AND user_id=? AND status='active'
        LIMIT 1
        """,
        (registry_id, user_id),
    ).fetchone()

    active_summary = _safe_json(active["summary_json"], {}) if active else {}
    active_is_adaptive = bool(active_summary.get("adaptive_candidate"))
    threshold = (active["activated_at"] or active["created_at"]) if active else None
    new_since_active = (
        sum(1 for row in rows if threshold and str(row.get("created_at") or "") > str(threshold))
        if threshold
        else count
    )

    total_remaining = max(0, MIN_TOTAL_SAMPLES - count)
    new_required = MIN_NEW_SAMPLES_AFTER_ADAPTATION if active_is_adaptive else 0
    new_remaining = max(0, new_required - new_since_active)
    ready = count >= MIN_TOTAL_SAMPLES and (not active_is_adaptive or new_since_active >= new_required)

    return {
        "sample_count": count,
        "approved_count": approved,
        "corrected_count": corrected,
        "minimum_samples": MIN_TOTAL_SAMPLES,
        "minimum_new_samples": new_required,
        "new_samples_since_active": new_since_active,
        "remaining_samples": max(total_remaining, new_remaining),
        "ready": ready,
        "active_is_adaptive": active_is_adaptive,
        "recipe_contract_version": RECIPE_CONTRACT_VERSION,
    }


def _split_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Deterministic holdout based on sample id.

    Primary rule: SHA256(sample_id) % 5 == 0 -> validation (~20%).
    If a small dataset happens to produce <4 validation rows, move the smallest
    stable hashes into validation until the floor is met.
    """
    ranked = []
    for row in rows:
        digest = hashlib.sha256(str(row["id"]).encode("utf-8")).hexdigest()
        ranked.append((digest, row))

    validation = [
        row for digest, row in ranked
        if int(digest[:8], 16) % 5 == 0
    ]
    train = [
        row for digest, row in ranked
        if int(digest[:8], 16) % 5 != 0
    ]

    if len(validation) < MIN_VALIDATION_SAMPLES:
        candidates = sorted(
            [(digest, row) for digest, row in ranked if row in train],
            key=lambda item: item[0],
        )
        needed = MIN_VALIDATION_SAMPLES - len(validation)
        moved = [row for _digest, row in candidates[:needed]]
        moved_ids = {row["id"] for row in moved}
        validation.extend(moved)
        train = [row for row in train if row["id"] not in moved_ids]

    return train, validation


def _mae(actual: list[float], predicted: list[float]) -> float:
    if not actual:
        return float("inf")
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def _candidate_clamped_value(key: str, base: float, residual: float) -> float:
    value = clamp_recipe_value(key, float(base) + float(residual))
    if value is None:
        return float(base)
    return float(value)


def _sample_matrix(rows: list[dict[str, Any]]):
    try:
        import numpy as np  # type: ignore
    except Exception as exc:
        raise RuntimeError("NumPy is required for adaptive retraining.") from exc

    if not rows:
        raise RuntimeError("No learning rows available.")
    feature_names, _first = _feature_vector(rows[0]["feature_record"])
    matrix = []
    for row in rows:
        names, vector = _feature_vector(row["feature_record"])
        if list(names) != list(feature_names):
            raise RuntimeError("Learning feature layout changed between samples.")
        matrix.append(vector)
    return feature_names, np.asarray(matrix, dtype=np.float32)


def build_adaptive_candidate(
    *,
    conn: sqlite3.Connection,
    data_dir: Path,
    ai_profiles_dir: Path,
    user_id: str,
    active_registry: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    try:
        import joblib  # type: ignore
        import numpy as np  # type: ignore
        from sklearn.ensemble import ExtraTreesRegressor  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Training dependencies are missing. Run install_training_lab.bat first."
        ) from exc

    active_version = active_registry.get("active_version")
    if not active_version:
        raise RuntimeError("No ACTIVE profile version.")

    learning_rows = _current_learning_rows(
        conn,
        user_id=user_id,
        registry_id=active_registry["id"],
    )
    if len(learning_rows) < MIN_TOTAL_SAMPLES:
        raise RuntimeError(
            f"Need at least {MIN_TOTAL_SAMPLES} current learning decisions."
        )

    train_rows, val_rows = _split_rows(learning_rows)
    if len(val_rows) < MIN_VALIDATION_SAMPLES or len(train_rows) < 12:
        raise RuntimeError("Learning split is too small for a safe candidate.")

    active_artifact_path = resolve_data_path(
        Path(data_dir),
        str(active_version["artifact_path"]),
    )
    active_manifest_path = resolve_data_path(
        Path(data_dir),
        str(active_version["manifest_path"]),
    )
    if not active_artifact_path.exists():
        raise RuntimeError("ACTIVE profile artifact is missing.")
    if not active_manifest_path.exists():
        raise RuntimeError("ACTIVE profile manifest is missing.")

    active_artifact = joblib.load(active_artifact_path)
    active_manifest = json.loads(active_manifest_path.read_text(encoding="utf-8"))

    expected_features = list(active_artifact.get("feature_names") or [])
    feature_names, X_train = _sample_matrix(train_rows)
    val_feature_names, X_val = _sample_matrix(val_rows)

    if expected_features and list(feature_names) != expected_features:
        raise RuntimeError("Learning samples do not match the ACTIVE Profile feature contract.")
    if list(val_feature_names) != list(feature_names):
        raise RuntimeError("Train/validation learning feature layouts do not match.")

    def enrich(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        base_predictions = predict_production_recipes_from_artifact(
            active_artifact,
            [row["feature_record"] for row in rows],
        )
        return [
            {
                **row,
                "base_recipe": prediction["recipe"],
                "final_recipe": row["photographer_recipe"],
            }
            for row, prediction in zip(rows, base_predictions)
        ]

    train = enrich(train_rows)
    validation = enrich(val_rows)

    output_targets = sorted(
        set().union(
            *[
                set(row["base_recipe"].keys()) & set(row["final_recipe"].keys())
                for row in learning_rows and (train + validation)
            ]
        )
    )

    residual_models: dict[str, Any] = {}
    residual_constants: dict[str, float] = {}
    target_metrics: dict[str, Any] = {}
    selected_targets: list[str] = []

    for target in output_targets:
        train_idx = [
            i for i, row in enumerate(train)
            if target in row["base_recipe"] and target in row["final_recipe"]
        ]
        val_idx = [
            i for i, row in enumerate(validation)
            if target in row["base_recipe"] and target in row["final_recipe"]
        ]

        if (
            len(train_idx) < MIN_TRAIN_SAMPLES_PER_TARGET
            or len(val_idx) < MIN_VALIDATION_SAMPLES_PER_TARGET
        ):
            target_metrics[target] = {
                "status": "insufficient_samples",
                "train_samples": len(train_idx),
                "validation_samples": len(val_idx),
            }
            continue

        y_delta_train = np.asarray(
            [
                float(train[i]["final_recipe"][target])
                - float(train[i]["base_recipe"][target])
                for i in train_idx
            ],
            dtype=np.float32,
        )

        nonzero_support = int(np.sum(np.abs(y_delta_train) > 0.0001))
        unique_residuals = len(set(round(float(v), 4) for v in y_delta_train.tolist()))
        if nonzero_support < MIN_NONZERO_SUPPORT_PER_TARGET:
            target_metrics[target] = {
                "status": "insufficient_corrections",
                "train_samples": len(train_idx),
                "validation_samples": len(val_idx),
                "nonzero_support": nonzero_support,
                "unique_residuals": unique_residuals,
            }
            continue

        actual = [
            float(validation[i]["final_recipe"][target])
            for i in val_idx
        ]
        base_pred = [
            float(validation[i]["base_recipe"][target])
            for i in val_idx
        ]

        model = None
        adaptation_type = "model"
        if unique_residuals == 1:
            adaptation_type = "constant"
            constant_residual = float(np.median(y_delta_train))
            residual_pred = [constant_residual] * len(val_idx)
        else:
            model = ExtraTreesRegressor(
                n_estimators=192,
                random_state=42,
                n_jobs=1,
                min_samples_leaf=2,
                max_features=0.80,
            )
            model.fit(X_train[train_idx], y_delta_train)
            residual_pred = model.predict(X_val[val_idx]).tolist()

        candidate_pred = [
            _candidate_clamped_value(target, base, residual)
            for base, residual in zip(base_pred, residual_pred)
        ]

        base_mae = _mae(actual, base_pred)
        candidate_mae = _mae(actual, candidate_pred)
        improvement = (
            (base_mae - candidate_mae) / base_mae * 100.0
            if base_mae > 1e-9
            else 0.0
        )

        selected = (
            candidate_mae < base_mae
            and improvement >= MIN_RELATIVE_IMPROVEMENT_PERCENT
        )

        target_metrics[target] = {
            "status": "selected" if selected else "rejected",
            "adaptation_type": adaptation_type,
            "train_samples": len(train_idx),
            "validation_samples": len(val_idx),
            "nonzero_support": nonzero_support,
            "unique_residuals": unique_residuals,
            "base_validation_mae": round(float(base_mae), 6),
            "candidate_validation_mae": round(float(candidate_mae), 6),
            "validation_improvement_percent": round(float(improvement), 2),
        }

        if selected:
            if adaptation_type == "constant":
                residual_constants[target] = float(np.median(y_delta_train))
            else:
                residual_models[target] = model
            selected_targets.append(target)

    if not selected_targets:
        return {
            "status": "no_improvement",
            "sample_count": len(learning_rows),
            "train_count": len(train),
            "validation_count": len(validation),
            "adapted_targets": [],
            "metrics": {
                "format": RETRAINING_FORMAT,
                "target_metrics": target_metrics,
                "selection_used_test": False,
                "selection_basis": "held_out_learning_validation_only",
            },
        }

    candidate_artifact = copy.deepcopy(active_artifact)
    candidate_artifact["learning_adaptation"] = {
        "format": ADAPTATION_FORMAT,
        "parent_version_id": active_version["id"],
        "parent_version_number": int(active_version["version_number"]),
        "recipe_contract_version": RECIPE_CONTRACT_VERSION,
        "feature_names": feature_names,
        "residual_models": residual_models,
        "residual_constants": residual_constants,
        "target_metrics": target_metrics,
        "sample_count": len(learning_rows),
        "train_count": len(train),
        "validation_count": len(validation),
        "train_sample_ids": [row["id"] for row in train],
        "validation_sample_ids": [row["id"] for row in validation],
        "selection_used_test": False,
    }

    staging_dir = (
        Path(ai_profiles_dir)
        / user_id
        / str(active_registry["source_profile_import_id"])
        / "retraining"
        / run_id
    )
    staging_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = staging_dir / "candidate_profile.joblib"
    manifest_path = staging_dir / "candidate_profile.json"
    joblib.dump(candidate_artifact, artifact_path)

    selected_metrics = [
        target_metrics[key]
        for key in selected_targets
        if target_metrics.get(key, {}).get("status") == "selected"
    ]
    mean_improvement = (
        sum(float(item["validation_improvement_percent"]) for item in selected_metrics)
        / len(selected_metrics)
        if selected_metrics
        else 0.0
    )

    manifest = copy.deepcopy(active_manifest)
    manifest["built_at"] = _utc_now()
    manifest["selection_basis"] = "held_out_learning_validation_only"
    manifest["test_used_for_selection"] = False
    manifest["learning_adaptation"] = {
        "format": ADAPTATION_FORMAT,
        "parent_version_id": active_version["id"],
        "parent_version_number": int(active_version["version_number"]),
        "sample_count": len(learning_rows),
        "train_count": len(train),
        "validation_count": len(validation),
        "adapted_targets": selected_targets,
        "target_metrics": target_metrics,
        "learning_sample_fingerprint": hashlib.sha256(
            "|".join(sorted(row["id"] for row in learning_rows)).encode("utf-8")
        ).hexdigest(),
        "selection_used_test": False,
    }

    old_summary = dict(manifest.get("summary") or {})
    manifest["summary"] = {
        **old_summary,
        "adaptive_candidate": True,
        "parent_version_number": int(active_version["version_number"]),
        "learning_samples": len(learning_rows),
        "learning_train_samples": len(train),
        "learning_validation_samples": len(validation),
        "adapted_target_count": len(selected_targets),
        "adapted_targets": selected_targets,
        "mean_selected_validation_improvement_percent": round(mean_improvement, 2),
        "learning_sample_fingerprint": manifest["learning_adaptation"]["learning_sample_fingerprint"],
    }
    manifest["artifact_path"] = str(artifact_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    registry_after = register_production_profile_snapshot(
        conn,
        data_dir=Path(data_dir),
        ai_profiles_dir=Path(ai_profiles_dir),
        user_id=user_id,
        source_profile_import_id=str(active_registry["source_profile_import_id"]),
        profile_name=str(active_registry.get("name") or "AI Profile"),
        production_manifest_path=manifest_path,
        production_artifact_path=artifact_path,
    )

    candidate_version = registry_after.get("latest_version")
    if not candidate_version:
        raise RuntimeError("Candidate profile version was not registered.")

    return {
        "status": "completed",
        "sample_count": len(learning_rows),
        "train_count": len(train),
        "validation_count": len(validation),
        "adapted_targets": selected_targets,
        "candidate_version": candidate_version,
        "metrics": {
            "format": RETRAINING_FORMAT,
            "selection_basis": "held_out_learning_validation_only",
            "selection_used_test": False,
            "target_metrics": target_metrics,
            "mean_selected_validation_improvement_percent": round(mean_improvement, 2),
        },
    }
