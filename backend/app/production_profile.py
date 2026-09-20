from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .profile_ai import _feature_vector, _read_jsonl
from .recipe_v2 import _inverse_target
from .recipes import (
    RECIPE_CONTRACT_VERSION,
    canonicalize_recipe,
    recipe_contract_public,
)


PRODUCTION_PROFILE_FORMAT = "prographer-production-ai-profile-v1"


def _infer_process_family_from_recipe_report(report: dict[str, Any]) -> str:
    counts = report.get("process_family_counts") or {}
    legacy = int(counts.get("legacy") or 0)
    modern = int(counts.get("modern") or 0)
    if legacy > modern and legacy > 0:
        return "legacy"
    if modern > legacy and modern > 0:
        return "modern"
    return "unknown"


def _infer_process_family_from_artifact(artifact: dict[str, Any]) -> str:
    explicit = str(artifact.get("process_family") or "").strip().lower()
    if explicit in {"legacy", "modern"}:
        return explicit

    emitted = set((artifact.get("fixed_outputs") or {}).keys())
    emitted.update((artifact.get("selected_models") or {}).keys())
    if emitted.intersection({"brightness", "recovery", "fill_light"}):
        return "legacy"
    return "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    values = sorted(float(v) for v in values)
    n = len(values)
    mid = n // 2
    if n % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _mae(actual, predicted) -> float:
    import numpy as np  # type: ignore

    a = np.asarray(actual, dtype=np.float64)
    p = np.asarray(predicted, dtype=np.float64)
    if a.size == 0:
        return float("inf")
    return float(np.mean(np.abs(a - p)))


def _native_predictions(source: str, key: str, model, transform: str, X):
    import numpy as np  # type: ignore

    raw = model.predict(X)
    if source == "v2" and transform == "reciprocal_temperature":
        return np.asarray(
            [_inverse_target(key, float(value)) for value in raw],
            dtype=np.float64,
        )
    return np.asarray(raw, dtype=np.float64)


def _candidate_sort_key(item: tuple[str, float]) -> tuple[float, int]:
    # Validation MAE is the only quality criterion.  Exact ties prefer the
    # simpler baseline, then V2 (canonical Recipe V2 semantics), then V1.
    priority = {"baseline": 0, "v2": 1, "v1": 2}
    source, mae = item
    return (round(float(mae), 12), priority.get(source, 99))


def build_production_profile_v1(
    *,
    profile_import_id: str,
    user_id: str,
    recipe_v2_dir: Path,
    recipe_report_path: Path,
    v1_model_path: Path,
    v2_model_path: Path,
    output_dir: Path,
    source_v1_run_id: Optional[str] = None,
    source_v2_run_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build ONE production profile from the existing research artifacts.

    Important rule: every model/baseline choice is made on the SAME canonical
    Recipe V2 VALIDATION rows. TEST is never read here.
    """
    try:
        import joblib  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Production Profile requires the training dependencies. Run install_training_lab.bat."
        ) from exc

    recipe_v2_dir = Path(recipe_v2_dir)
    recipe_report_path = Path(recipe_report_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for required in (recipe_report_path, v1_model_path, v2_model_path):
        if not Path(required).exists():
            raise RuntimeError(f"Required Production Profile source is missing: {required}")

    report = json.loads(recipe_report_path.read_text(encoding="utf-8"))
    process_family = _infer_process_family_from_recipe_report(report)
    if not isinstance(report.get("learnability"), dict):
        raise RuntimeError("Recipe V2.2 Learnability report is missing.")

    train_rows = _read_jsonl(recipe_v2_dir / "train.jsonl")
    validation_rows = _read_jsonl(recipe_v2_dir / "validation.jsonl")
    if not train_rows or not validation_rows:
        raise RuntimeError("Canonical Recipe V2 TRAIN/VALIDATION data is missing.")

    v1 = joblib.load(Path(v1_model_path))
    v2 = joblib.load(Path(v2_model_path))
    v1_models = v1.get("models") or {}
    v2_models = v2.get("models") or {}
    v2_transforms = v2.get("target_transforms") or {}

    feature_names, _ = _feature_vector(validation_rows[0])
    for label, artifact in (("V1", v1), ("V2", v2)):
        artifact_features = artifact.get("feature_names") or []
        if artifact_features and list(artifact_features) != list(feature_names):
            raise RuntimeError(f"{label} feature layout does not match the canonical Vision feature contract.")

    X_validation = np.asarray(
        [_feature_vector(row)[1] for row in validation_rows],
        dtype=np.float32,
    )

    learnability = report.get("learnability") or {}
    constants_from_artifact = v2.get("constant_profile_values") or {}
    parameters: dict[str, Any] = {}
    selected_models: dict[str, Any] = {}
    output_values: dict[str, Any] = {}

    model_count = 0
    baseline_count = 0
    constant_count = 0
    excluded_count = 0

    for key, guard in learnability.items():
        status = str((guard or {}).get("status") or "unsupported")
        reason = str((guard or {}).get("reason") or status)

        train_values = [
            float(row["develop_recipe_v2"][key])
            for row in train_rows
            if key in (row.get("develop_recipe_v2") or {})
        ]
        baseline_value = _median(train_values) if train_values else None

        if status == "constant":
            value = constants_from_artifact.get(key)
            if value is None:
                value = (guard or {}).get("constant_value")
            if value is None:
                value = baseline_value
            if value is None:
                parameters[key] = {
                    "state": "excluded",
                    "source": None,
                    "reason": "constant_without_value",
                    "guard_status": status,
                }
                excluded_count += 1
                continue
            output_values[key] = {"source": "constant", "value": float(value)}
            parameters[key] = {
                "state": "constant",
                "source": "constant",
                "value": float(value),
                "reason": "recipe_guard_constant",
                "guard_status": status,
                "selection_used_test": False,
            }
            constant_count += 1
            continue

        if status != "trainable":
            parameters[key] = {
                "state": "excluded",
                "source": None,
                "reason": reason,
                "guard_status": status,
                "selection_used_test": False,
            }
            excluded_count += 1
            continue

        validation_idx = [
            i for i, row in enumerate(validation_rows)
            if key in (row.get("develop_recipe_v2") or {})
        ]
        if not validation_idx or baseline_value is None:
            parameters[key] = {
                "state": "excluded",
                "source": None,
                "reason": "missing_canonical_validation_target",
                "guard_status": status,
                "selection_used_test": False,
            }
            excluded_count += 1
            continue

        y = np.asarray(
            [float(validation_rows[i]["develop_recipe_v2"][key]) for i in validation_idx],
            dtype=np.float64,
        )
        candidates: dict[str, float] = {
            "baseline": _mae(y, np.full_like(y, float(baseline_value))),
        }

        if key in v1_models:
            pred = _native_predictions(
                "v1", key, v1_models[key], "identity", X_validation[validation_idx]
            )
            candidates["v1"] = _mae(y, pred)

        if key in v2_models:
            transform = str(v2_transforms.get(key) or "identity")
            pred = _native_predictions(
                "v2", key, v2_models[key], transform, X_validation[validation_idx]
            )
            candidates["v2"] = _mae(y, pred)

        winner, winner_mae = min(candidates.items(), key=_candidate_sort_key)
        candidate_metrics = {
            name: round(float(mae), 6)
            for name, mae in sorted(candidates.items())
        }

        if winner == "baseline":
            output_values[key] = {"source": "baseline", "value": float(baseline_value)}
            parameters[key] = {
                "state": "baseline",
                "source": "baseline",
                "value": float(baseline_value),
                "validation_samples": len(validation_idx),
                "validation_mae": round(float(winner_mae), 6),
                "candidate_validation_mae": candidate_metrics,
                "reason": "lowest_canonical_validation_mae",
                "guard_status": status,
                "selection_used_test": False,
            }
            baseline_count += 1
            continue

        if winner == "v1":
            selected_models[key] = {
                "source": "v1",
                "model": v1_models[key],
                "transform": "identity",
            }
        else:
            selected_models[key] = {
                "source": "v2",
                "model": v2_models[key],
                "transform": str(v2_transforms.get(key) or "identity"),
            }

        parameters[key] = {
            "state": "model",
            "source": winner,
            "validation_samples": len(validation_idx),
            "validation_mae": round(float(winner_mae), 6),
            "candidate_validation_mae": candidate_metrics,
            "reason": "lowest_canonical_validation_mae",
            "guard_status": status,
            "selection_used_test": False,
        }
        model_count += 1

    ready = model_count > 0 and (model_count + baseline_count + constant_count) > 0
    if not ready:
        raise RuntimeError("Production Profile could not select any usable edit parameters.")

    artifact = {
        "profile_format": PRODUCTION_PROFILE_FORMAT,
        "recipe_contract_version": RECIPE_CONTRACT_VERSION,
        "profile_import_id": profile_import_id,
        "user_id": user_id,
        "feature_names": feature_names,
        "process_family": process_family,
        "selected_models": selected_models,
        "fixed_outputs": output_values,
        "parameters": parameters,
    }
    artifact_path = output_dir / "production_profile_v1.joblib"
    joblib.dump(artifact, artifact_path)

    manifest = {
        "profile_format": PRODUCTION_PROFILE_FORMAT,
        "recipe_contract": recipe_contract_public(),
        "profile_import_id": profile_import_id,
        "process_family": process_family,
        "built_at": _utc_now(),
        "selection_basis": "canonical_recipe_v2_validation_only",
        "test_used_for_selection": False,
        "source_runs": {
            "context_model_v1": source_v1_run_id,
            "context_model_v2": source_v2_run_id,
        },
        "artifact_path": str(artifact_path),
        "summary": {
            "ready_for_inference": ready,
            "model_targets": model_count,
            "baseline_targets": baseline_count,
            "constant_targets": constant_count,
            "excluded_targets": excluded_count,
            "production_outputs": model_count + baseline_count + constant_count,
        },
        "parameters": parameters,
        "contract_rules": {
            "temperature": "absolute Kelvin only",
            "test_policy": "TEST is never used to choose a production source",
            "excluded_targets": "not emitted by production inference",
            "baseline_targets": "emit the TRAIN median because it beat every available model on canonical VALIDATION",
            "constant_targets": "emit the Recipe Guard constant without a model",
        },
    }
    manifest_path = output_dir / "production_profile_v1.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def predict_production_recipes_from_artifact(
    artifact: dict[str, Any],
    vision_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    try:
        import numpy as np  # type: ignore
    except Exception as exc:
        raise RuntimeError("Production inference dependencies are missing.") from exc

    if not vision_records:
        return []

    expected = artifact.get("feature_names") or []
    vectors = []
    actual_names = None
    for record in vision_records:
        names, vector = _feature_vector(record)
        if actual_names is None:
            actual_names = list(names)
        elif list(names) != actual_names:
            raise RuntimeError("Vision feature layout changed between records.")
        vectors.append(vector)

    if expected and list(expected) != list(actual_names or []):
        raise RuntimeError("Vision feature layout does not match the active Production Profile.")

    X = np.asarray(vectors, dtype=np.float32)
    recipes: list[dict[str, float]] = [dict() for _ in vision_records]

    for key, fixed in (artifact.get("fixed_outputs") or {}).items():
        value = float(fixed["value"])
        for recipe in recipes:
            recipe[key] = value

    for key, selected in (artifact.get("selected_models") or {}).items():
        raw_values = selected["model"].predict(X)
        for idx, raw_value in enumerate(raw_values):
            raw = float(raw_value)
            if selected.get("source") == "v2" and selected.get("transform") == "reciprocal_temperature":
                value = float(_inverse_target(key, raw))
            else:
                value = raw
            recipes[idx][key] = value

    adaptation = artifact.get("learning_adaptation") or {}
    residual_models = adaptation.get("residual_models") or {}
    residual_constants = adaptation.get("residual_constants") or {}
    if residual_models or residual_constants:
        adaptation_features = adaptation.get("feature_names") or expected
        if adaptation_features and list(adaptation_features) != list(actual_names or []):
            raise RuntimeError("Learning adaptation feature layout does not match the active Profile.")

        for key, residual in residual_constants.items():
            for idx in range(len(recipes)):
                if key in recipes[idx]:
                    recipes[idx][key] = float(recipes[idx][key]) + float(residual)

        for key, model in residual_models.items():
            residual_values = model.predict(X)
            for idx, residual in enumerate(residual_values):
                if key in recipes[idx]:
                    recipes[idx][key] = float(recipes[idx][key]) + float(residual)

    return [
        {
            "profile_format": artifact.get("profile_format"),
            "recipe_contract_version": artifact.get("recipe_contract_version"),
            "process_family": _infer_process_family_from_artifact(artifact),
            "learning_adaptation_format": adaptation.get("format"),
            "recipe": canonicalize_recipe(recipe),
        }
        for recipe in recipes
    ]


def predict_production_recipe_from_artifact(
    artifact: dict[str, Any],
    vision_record: dict[str, Any],
) -> dict[str, Any]:
    predictions = predict_production_recipes_from_artifact(artifact, [vision_record])
    if not predictions:
        raise RuntimeError("No production prediction was produced.")
    return predictions[0]


def predict_production_recipe(
    artifact_path: Path,
    vision_record: dict[str, Any],
) -> dict[str, Any]:
    """Single production prediction entry point for an immutable Profile artifact."""
    try:
        import joblib  # type: ignore
    except Exception as exc:
        raise RuntimeError("Production inference dependencies are missing.") from exc

    artifact = joblib.load(Path(artifact_path))
    return predict_production_recipe_from_artifact(artifact, vision_record)
