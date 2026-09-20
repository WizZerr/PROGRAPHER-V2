from __future__ import annotations

import json
import math
import math
from pathlib import Path
from typing import Any, Callable, Optional

from .profile_ai import _feature_vector, _read_jsonl


ProgressFn = Callable[[str, int, dict[str, Any]], None]

# V2 intentionally keeps legacy Lightroom controls separate instead of
# pretending Recovery == Highlights or FillLight == Shadows.
V2_TARGET_KEYS = [
    "exposure",
    "contrast",
    "highlights",
    "shadows",
    "whites",
    "blacks",
    "temperature",
    "tint",
    "clarity",
    "vibrance",
    "saturation",
    "brightness",
    "recovery",
    "fill_light",
]

ALIASES = {
    "exposure": ["Exposure2012", "Exposure"],
    "contrast": ["Contrast2012", "Contrast"],
    "highlights": ["Highlights2012", "Highlights"],
    "shadows": ["Shadows2012", "Shadows"],
    "whites": ["Whites2012", "Whites"],
    "blacks": ["Blacks2012", "Blacks"],
    "temperature": ["Temperature"],
    "tint": ["Tint"],
    "clarity": ["Clarity2012", "Clarity"],
    "vibrance": ["Vibrance"],
    "saturation": ["Saturation"],
    "brightness": ["Brightness"],
    "recovery": ["Recovery"],
    "fill_light": ["FillLight", "Fill Light"],
    "process_version": ["ProcessVersion"],
}

# Adobe PV2003/PV2010 legacy defaults. These are applied only after the
# payload is identified as legacy. They are not injected into modern PV2012+
# samples.
LEGACY_DEFAULTS = {
    "contrast": 25.0,
    "blacks": 5.0,
    "brightness": 50.0,
    "clarity": 0.0,
    "vibrance": 0.0,
    "saturation": 0.0,
    "recovery": 0.0,
    "fill_light": 0.0,
}

MODERN_ZERO_DEFAULTS = {
    "exposure": 0.0,
    "contrast": 0.0,
    "highlights": 0.0,
    "shadows": 0.0,
    "whites": 0.0,
    "blacks": 0.0,
    "clarity": 0.0,
    "vibrance": 0.0,
    "saturation": 0.0,
}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _leaf_lookup(settings: dict[str, Any]) -> dict[str, Any]:
    lookup: dict[str, Any] = {}
    for raw_key, value in (settings or {}).items():
        leaf = str(raw_key).split(".")[-1].split(":")[-1].strip()
        if leaf:
            lookup.setdefault(leaf.casefold(), value)
    return lookup


def _numeric(value) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except Exception:
        return None
    return None


def _lookup_alias(lookup: dict[str, Any], aliases: list[str]) -> tuple[Optional[float], Optional[str]]:
    for alias in aliases:
        key = alias.casefold()
        if key in lookup:
            number = _numeric(lookup[key])
            if number is not None:
                return number, alias
    return None, None


def _lookup_text(lookup: dict[str, Any], aliases: list[str]) -> Optional[str]:
    for alias in aliases:
        key = alias.casefold()
        if key in lookup and lookup[key] is not None:
            return str(lookup[key])
    return None


def detect_process_family(settings: dict[str, Any]) -> tuple[str, str]:
    lookup = _leaf_lookup(settings)
    keys = set(lookup)

    modern_markers = {
        "exposure2012", "contrast2012", "highlights2012",
        "shadows2012", "whites2012", "blacks2012",
    }
    legacy_markers = {
        "recovery", "filllight", "brightness",
    }

    process_version = _lookup_text(lookup, ALIASES["process_version"]) or ""

    if keys & modern_markers:
        return "modern", process_version
    if keys & legacy_markers:
        return "legacy", process_version

    pv = process_version.casefold()
    if "2012" in pv or "6.7" in pv or "6.6" in pv:
        return "modern", process_version

    # FiveK and old Lightroom catalogs can omit ProcessVersion while exposing
    # only the pre-2012 control family. Do not assume modern controls.
    if any(key in keys for key in ("brightness", "recovery", "filllight")):
        return "legacy", process_version

    return "unknown", process_version


def normalize_recipe_v2(sample: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
    settings = sample.get("develop_settings") or {}
    v1 = sample.get("develop_recipe") or {}
    lookup = _leaf_lookup(settings)
    family, process_version = detect_process_family(settings)

    recipe: dict[str, float] = {}
    source_map: dict[str, str] = {}
    default_filled: list[str] = []

    # Prefer explicit scalar settings, then the already-normalized V1 recipe.
    for target in V2_TARGET_KEYS:
        value, alias = _lookup_alias(lookup, ALIASES.get(target, [target]))
        if value is not None:
            recipe[target] = value
            source_map[target] = f"explicit:{alias}"
            continue

        fallback = _numeric(v1.get(target))
        if fallback is not None:
            recipe[target] = fallback
            source_map[target] = "v1_normalized"

    # Complete only defaults that are valid for the detected Lightroom family.
    defaults: dict[str, float] = {}
    if family == "legacy":
        defaults.update(LEGACY_DEFAULTS)
    elif family == "modern":
        defaults.update(MODERN_ZERO_DEFAULTS)

    # Saturation / clarity / vibrance default to zero across the supported
    # Lightroom families. For unknown catalogs, only complete these safe
    # cross-version defaults.
    if family == "unknown":
        defaults.update({
            "clarity": 0.0,
            "vibrance": 0.0,
            "saturation": 0.0,
        })

    for key, value in defaults.items():
        if key not in recipe:
            recipe[key] = value
            source_map[key] = f"default:{family}"
            default_filled.append(key)

    # Keep raw Kelvin in the recipe for export/display. Training V2 transforms
    # it to reciprocal temperature (mired-like 1e6/K), which behaves much
    # better around extreme warm/cool targets and is exactly reversible.
    temperature = recipe.get("temperature")
    temperature_mired = None
    if temperature is not None and temperature > 0:
        temperature_mired = 1_000_000.0 / temperature

    diagnostics = {
        "process_family": family,
        "process_version": process_version,
        "source_map": source_map,
        "default_filled": default_filled,
        "temperature_mired": temperature_mired,
    }
    return recipe, diagnostics


def _distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "min": None, "p01": None, "median": None,
            "p90": None, "p99": None, "max": None,
            "extreme_count": 0,
        }
    try:
        import numpy as np  # type: ignore
    except Exception as exc:
        raise RuntimeError("numpy is required for Recipe Intelligence V2.") from exc

    arr = np.asarray(values, dtype=np.float64)
    p01 = float(np.percentile(arr, 1))
    p99 = float(np.percentile(arr, 99))
    extreme_count = int(np.sum((arr < p01) | (arr > p99)))
    return {
        "count": int(len(arr)),
        "min": round(float(np.min(arr)), 6),
        "p01": round(p01, 6),
        "median": round(float(np.median(arr)), 6),
        "p90": round(float(np.percentile(arr, 90)), 6),
        "p99": round(p99, 6),
        "max": round(float(np.max(arr)), 6),
        "extreme_count": extreme_count,
    }


def build_recipe_v2_dataset(
    dataset_dir: Path,
    vision_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    dataset_dir = Path(dataset_dir)
    vision_dir = Path(vision_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_split_rows: dict[str, list[dict[str, Any]]] = {}
    report_split_counts: dict[str, int] = {}
    process_counts = {"legacy": 0, "modern": 0, "unknown": 0}
    default_fill_counts: dict[str, int] = {key: 0 for key in V2_TARGET_KEYS}

    coverage_before: dict[str, int] = {key: 0 for key in V2_TARGET_KEYS}
    coverage_after: dict[str, int] = {key: 0 for key in V2_TARGET_KEYS}
    train_values: dict[str, list[float]] = {key: [] for key in V2_TARGET_KEYS}
    temperature_mired_values: list[float] = []

    provenance_all: dict[str, dict[str, int]] = {key: {} for key in V2_TARGET_KEYS}
    provenance_train: dict[str, dict[str, int]] = {key: {} for key in V2_TARGET_KEYS}
    family_counts_by_target: dict[str, dict[str, int]] = {
        key: {"legacy": 0, "modern": 0, "unknown": 0}
        for key in V2_TARGET_KEYS
    }

    for split in ("train", "validation", "test"):
        source_rows = _read_jsonl(dataset_dir / f"{split}.jsonl")
        vision_rows = _read_jsonl(vision_dir / f"{split}.jsonl")
        by_id = {str(row.get("sample_id")): row for row in source_rows}

        enriched: list[dict[str, Any]] = []
        for vision_row in vision_rows:
            sid = str(vision_row.get("sample_id") or "")
            original = by_id.get(sid)
            if original is None:
                raise RuntimeError(f"Recipe V2 mapping failed: sample {sid} missing from Dataset.")

            v1_recipe = original.get("develop_recipe") or {}
            for key in V2_TARGET_KEYS:
                if key in v1_recipe:
                    coverage_before[key] += 1

            recipe_v2, diagnostics = normalize_recipe_v2(original)
            family = diagnostics["process_family"]
            process_counts[family] = process_counts.get(family, 0) + 1

            for key in diagnostics["default_filled"]:
                default_fill_counts[key] = default_fill_counts.get(key, 0) + 1

            for key, value in recipe_v2.items():
                if key in coverage_after:
                    coverage_after[key] += 1

                    source = str((diagnostics.get("source_map") or {}).get(key) or "unknown")
                    provenance_all[key][source] = provenance_all[key].get(source, 0) + 1
                    family_counts_by_target[key][family] = family_counts_by_target[key].get(family, 0) + 1

                    if split == "train":
                        train_values[key].append(float(value))
                        provenance_train[key][source] = provenance_train[key].get(source, 0) + 1

            if split == "train" and diagnostics.get("temperature_mired") is not None:
                temperature_mired_values.append(float(diagnostics["temperature_mired"]))

            row = dict(vision_row)
            row["develop_recipe_v1"] = vision_row.get("develop_recipe") or {}
            row["develop_recipe_v2"] = recipe_v2
            row["recipe_v2_diagnostics"] = diagnostics
            enriched.append(row)

        _write_jsonl(output_dir / f"{split}.jsonl", enriched)
        all_split_rows[split] = enriched
        report_split_counts[split] = len(enriched)

    train_total = max(1, report_split_counts.get("train", 0))
    full_total = sum(report_split_counts.values())

    coverage: dict[str, Any] = {}
    distributions: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    learnability: dict[str, Any] = {}
    constant_profile_values: dict[str, float] = {}

    trainable_count = 0
    constant_count = 0
    sparse_count = 0
    suspicious_count = 0
    unsupported_count = 0

    for key in V2_TARGET_KEYS:
        before = coverage_before[key]
        after = coverage_after[key]
        values = train_values[key]
        train_percent = len(values) / train_total * 100.0
        dist = _distribution(values)
        distributions[key] = dist

        source_counts_all = dict(
            sorted(provenance_all[key].items(), key=lambda item: item[1], reverse=True)
        )
        source_counts_train = dict(
            sorted(provenance_train[key].items(), key=lambda item: item[1], reverse=True)
        )
        top_source = next(iter(source_counts_train), None)

        explicit_count = sum(
            count for source, count in source_counts_train.items()
            if source.startswith("explicit:")
        )
        default_count = sum(
            count for source, count in source_counts_train.items()
            if source.startswith("default:")
        )
        v1_fallback_count = int(source_counts_train.get("v1_normalized", 0))
        unknown_source_count = int(source_counts_train.get("unknown", 0))

        rounded_values = [round(float(value), 6) for value in values]
        rounded_unique = sorted(set(rounded_values))
        unique_count = len(rounded_unique)
        value_range = (
            float(max(values) - min(values))
            if values else 0.0
        )

        # Sparse Target Guard:
        # a target may technically vary while almost every sample is the same
        # default value (e.g. 3999 x Clarity=0 and 1 x Clarity=20).
        # Such a target should not be learned from one/few positive examples.
        value_counts: dict[float, int] = {}
        for rounded_value in rounded_values:
            value_counts[rounded_value] = value_counts.get(rounded_value, 0) + 1

        dominant_value = None
        dominant_count = 0
        if value_counts:
            dominant_value, dominant_count = max(
                value_counts.items(),
                key=lambda item: item[1],
            )

        variation_support_count = max(0, len(values) - dominant_count)
        variation_support_percent = (
            variation_support_count / max(1, len(values)) * 100.0
        )

        # Require both a practical absolute floor and ~1% of TRAIN.
        # FiveK/4,000 TRAIN => 40 examples. This is deliberately conservative:
        # we would rather skip a weak target than teach a misleading rule.
        minimum_variation_support = max(
            25,
            int(math.ceil(train_total * 0.01)),
        )

        legacy_count = int(family_counts_by_target[key].get("legacy", 0))
        modern_count = int(family_counts_by_target[key].get("modern", 0))
        unknown_family_count = int(family_counts_by_target[key].get("unknown", 0))

        suspicious_reason = None

        # In pre-2012 Lightroom, a scalar called "Shadows" can refer to a
        # parametric tone-curve region rather than the modern Basic-panel
        # Shadows control. V1 normalized this name too aggressively. Never
        # train it until provenance proves it is Shadows2012 / modern.
        if key == "shadows" and legacy_count > 0:
            suspicious_reason = (
                "legacy_shadows_is_ambiguous_and_may_be_tone_curve"
            )

        coverage_ok = train_percent >= 50.0
        constant = (
            coverage_ok
            and bool(values)
            and (unique_count <= 1 or abs(value_range) <= 1e-9)
        )
        sparse = (
            coverage_ok
            and bool(values)
            and not constant
            and variation_support_count < minimum_variation_support
        )

        if suspicious_reason:
            status = "suspicious"
            reason = suspicious_reason
            suspicious_count += 1
        elif not coverage_ok:
            status = "unsupported"
            reason = "insufficient_target_coverage"
            unsupported_count += 1
        elif constant:
            status = "constant"
            reason = "no_meaningful_variation"
            constant_count += 1
            constant_profile_values[key] = float(dist["median"])
        elif sparse:
            status = "sparse"
            reason = "insufficient_variation_support"
            sparse_count += 1
        else:
            status = "trainable"
            reason = "verified_variable_target"
            trainable_count += 1

        provenance[key] = {
            "top_source": top_source,
            "source_counts_all_splits": source_counts_all,
            "source_counts_train": source_counts_train,
            "explicit_count_train": explicit_count,
            "default_count_train": default_count,
            "v1_fallback_count_train": v1_fallback_count,
            "unknown_source_count_train": unknown_source_count,
            "legacy_count_all_splits": legacy_count,
            "modern_count_all_splits": modern_count,
            "unknown_family_count_all_splits": unknown_family_count,
            "unique_value_count_train": unique_count,
            "value_range_train": round(value_range, 6),
            "dominant_value_train": dominant_value,
            "dominant_count_train": dominant_count,
            "dominant_percent_train": round(
                dominant_count / max(1, len(values)) * 100.0,
                4,
            ),
            "variation_support_count_train": variation_support_count,
            "variation_support_percent_train": round(
                variation_support_percent,
                4,
            ),
            "minimum_variation_support_required": minimum_variation_support,
        }

        learnability[key] = {
            "status": status,
            "reason": reason,
            "train_percent": round(train_percent, 2),
            "train_count": len(values),
            "train_total": train_total,
            "constant_value": (
                float(dist["median"]) if status == "constant" else None
            ),
            "top_source": top_source,
            "explicit_percent_train": round(explicit_count / train_total * 100.0, 2),
            "default_percent_train": round(default_count / train_total * 100.0, 2),
            "v1_fallback_percent_train": round(v1_fallback_count / train_total * 100.0, 2),
            "unique_value_count_train": unique_count,
            "value_range_train": round(value_range, 6),
            "dominant_value_train": dominant_value,
            "dominant_percent_train": round(
                dominant_count / max(1, len(values)) * 100.0,
                4,
            ),
            "variation_support_count_train": variation_support_count,
            "variation_support_percent_train": round(
                variation_support_percent,
                4,
            ),
            "minimum_variation_support_required": minimum_variation_support,
        }

        coverage[key] = {
            "v1_count_all_splits": before,
            "v2_count_all_splits": after,
            "v1_percent_all_splits": round(before / max(1, full_total) * 100.0, 2),
            "v2_percent_all_splits": round(after / max(1, full_total) * 100.0, 2),
            "train_count": len(values),
            "train_percent": round(train_percent, 2),
            "default_filled_all_splits": default_fill_counts.get(key, 0),
            "train_eligible": status == "trainable",
        }

    guard = {
        "trainable_count": trainable_count,
        "constant_count": constant_count,
        "sparse_count": sparse_count,
        "suspicious_count": suspicious_count,
        "unsupported_count": unsupported_count,
        "ready_for_training": trainable_count > 0,
        "suspicious_targets_are_excluded": True,
        "sparse_targets_are_excluded": True,
        "constant_targets_are_stored_without_model_training": True,
        "sparse_policy": {
            "minimum_absolute_variation_support": 25,
            "minimum_train_fraction": 0.01,
            "effective_required_for_this_dataset": max(
                25,
                int(math.ceil(train_total * 0.01)),
            ),
        },
    }

    report = {
        "recipe_version": "prographer-recipe-v2.2",
        "splits": report_split_counts,
        "total_samples": full_total,
        "process_family_counts": process_counts,
        "coverage": coverage,
        "distributions": distributions,
        "provenance": provenance,
        "learnability": learnability,
        "constant_profile_values": constant_profile_values,
        "guard": guard,
        "temperature": {
            "training_representation": "reciprocal_temperature_1e6_over_kelvin",
            "native_unit": "kelvin",
            "transformed_distribution": _distribution(temperature_mired_values),
            "native_distribution": distributions.get("temperature"),
            "extremes_preserved": True,
        },
        "rules": {
            "legacy_defaults_completed": LEGACY_DEFAULTS,
            "modern_zero_defaults_completed": MODERN_ZERO_DEFAULTS,
            "modern_and_legacy_controls_are_not_falsely_merged": True,
            "test_split_unchanged": True,
        },
    }

    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def _target_value(recipe: dict[str, Any], key: str, transformed: bool) -> Optional[float]:
    if key not in recipe:
        return None
    try:
        value = float(recipe[key])
    except Exception:
        return None

    if transformed and key == "temperature":
        if value <= 0:
            return None
        return 1_000_000.0 / value
    return value


def _inverse_target(key: str, value: float) -> float:
    if key == "temperature":
        if value <= 1e-9:
            return 1_000_000.0
        return 1_000_000.0 / value
    return value


def train_context_model_v2(
    recipe_v2_dir: Path,
    model_dir: Path,
    v1_evaluation_path: Optional[Path] = None,
    progress: Optional[ProgressFn] = None,
) -> dict[str, Any]:
    try:
        import joblib  # type: ignore
        import numpy as np  # type: ignore
        from sklearn.ensemble import ExtraTreesRegressor  # type: ignore
        from sklearn.metrics import mean_absolute_error  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Training dependencies are missing. Run install_training_lab.bat first."
        ) from exc

    recipe_v2_dir = Path(recipe_v2_dir)
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    train = _read_jsonl(recipe_v2_dir / "train.jsonl")
    validation = _read_jsonl(recipe_v2_dir / "validation.jsonl")
    test = _read_jsonl(recipe_v2_dir / "test.jsonl")
    if not train or not validation or not test:
        raise RuntimeError("Recipe V2 splits are incomplete.")

    def emit(stage: str, pct: int, details: dict[str, Any]):
        if progress:
            progress(stage, pct, details)

    emit("loading_recipe_v2", 3, {
        "train": len(train),
        "validation": len(validation),
        "test": len(test),
    })

    feature_names, _ = _feature_vector(train[0])
    X_train = np.asarray([_feature_vector(row)[1] for row in train], dtype=np.float32)
    X_val = np.asarray([_feature_vector(row)[1] for row in validation], dtype=np.float32)
    X_test = np.asarray([_feature_vector(row)[1] for row in test], dtype=np.float32)

    report_path = recipe_v2_dir / "report.json"
    if not report_path.exists():
        raise RuntimeError("Recipe V2 provenance report is missing.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    learnability = report.get("learnability") or {}
    constant_profile_values = report.get("constant_profile_values") or {}

    eligible = [
        key for key in V2_TARGET_KEYS
        if (learnability.get(key) or {}).get("status") == "trainable"
    ]

    if not eligible:
        raise RuntimeError("Target Provenance Guard found no verified trainable targets.")

    models: dict[str, Any] = {}
    validation_metrics: dict[str, Any] = {}

    # Keep the same model family as V1 so the experiment isolates Recipe V2
    # rather than conflating target improvements with a new architecture.
    for index, key in enumerate(eligible):
        train_idx = [
            i for i, row in enumerate(train)
            if _target_value(row.get("develop_recipe_v2") or {}, key, transformed=True) is not None
        ]
        val_idx = [
            i for i, row in enumerate(validation)
            if _target_value(row.get("develop_recipe_v2") or {}, key, transformed=True) is not None
        ]
        if len(train_idx) < 100 or len(val_idx) < 20:
            continue

        y_train_native = np.asarray(
            [float(train[i]["develop_recipe_v2"][key]) for i in train_idx],
            dtype=np.float64,
        )
        y_val_native = np.asarray(
            [float(validation[i]["develop_recipe_v2"][key]) for i in val_idx],
            dtype=np.float64,
        )

        y_train_fit = np.asarray(
            [_target_value(train[i]["develop_recipe_v2"], key, transformed=True) for i in train_idx],
            dtype=np.float64,
        )

        model = ExtraTreesRegressor(
            n_estimators=256,
            random_state=42,
            n_jobs=-1,
            min_samples_leaf=2,
            max_features=0.80,
        )
        model.fit(X_train[train_idx], y_train_fit)

        pred_fit = model.predict(X_val[val_idx])
        pred_native = np.asarray([_inverse_target(key, float(v)) for v in pred_fit], dtype=np.float64)

        val_mae = float(mean_absolute_error(y_val_native, pred_native))
        baseline_native = float(np.median(y_train_native))
        baseline_mae = float(
            mean_absolute_error(y_val_native, np.full_like(y_val_native, baseline_native))
        )
        improvement = (
            (baseline_mae - val_mae) / baseline_mae * 100.0
            if baseline_mae > 1e-9 else 0.0
        )

        models[key] = model
        validation_metrics[key] = {
            "train_samples": len(train_idx),
            "validation_samples": len(val_idx),
            "validation_mae_native": round(val_mae, 6),
            "validation_baseline_mae_native": round(baseline_mae, 6),
            "validation_improvement_percent": round(improvement, 2),
            "target_median_native": round(baseline_native, 6),
            "training_transform": "reciprocal_temperature" if key == "temperature" else "identity",
        }

        emit("training_recipe_v2", 8 + int((index + 1) / len(eligible) * 60), {
            "parameter": key,
            "trained_parameters": len(models),
            "parameter_total": len(eligible),
        })

    if not models:
        raise RuntimeError("Recipe V2 could not train any parameter model.")

    emit("locking_v2_model", 72, {"trained_parameters": len(models)})

    test_metrics: dict[str, Any] = {}
    for index, (key, model) in enumerate(models.items()):
        test_idx = [
            i for i, row in enumerate(test)
            if _target_value(row.get("develop_recipe_v2") or {}, key, transformed=True) is not None
        ]
        if not test_idx:
            continue

        y_test_native = np.asarray(
            [float(test[i]["develop_recipe_v2"][key]) for i in test_idx],
            dtype=np.float64,
        )
        pred_fit = model.predict(X_test[test_idx])
        pred_native = np.asarray([_inverse_target(key, float(v)) for v in pred_fit], dtype=np.float64)
        mae = float(mean_absolute_error(y_test_native, pred_native))

        train_native = np.asarray(
            [
                float(row["develop_recipe_v2"][key])
                for row in train
                if key in (row.get("develop_recipe_v2") or {})
            ],
            dtype=np.float64,
        )
        baseline_native = float(np.median(train_native))
        baseline_mae = float(
            mean_absolute_error(y_test_native, np.full_like(y_test_native, baseline_native))
        )
        improvement = (
            (baseline_mae - mae) / baseline_mae * 100.0
            if baseline_mae > 1e-9 else 0.0
        )

        test_metrics[key] = {
            "samples": len(test_idx),
            "mae_native": round(mae, 6),
            "baseline_mae_native": round(baseline_mae, 6),
            "improvement_percent": round(improvement, 2),
            "training_transform": "reciprocal_temperature" if key == "temperature" else "identity",
        }

        emit("testing_v2_locked_set", 74 + int((index + 1) / len(models) * 20), {
            "parameter": key,
            "tested_parameters": index + 1,
            "parameter_total": len(models),
        })

    v1_stats: dict[str, Any] = {}
    if v1_evaluation_path and Path(v1_evaluation_path).exists():
        try:
            v1_eval = json.loads(Path(v1_evaluation_path).read_text(encoding="utf-8"))
            v1_stats = v1_eval.get("parameter_stats") or {}
        except Exception:
            v1_stats = {}

    comparison: dict[str, Any] = {}
    for key, v2 in test_metrics.items():
        v1 = v1_stats.get(key)
        v1_mae = float(v1["mae"]) if isinstance(v1, dict) and v1.get("mae") is not None else None
        v2_mae = float(v2["mae_native"])
        delta = None
        if v1_mae is not None and v1_mae > 1e-9:
            delta = (v1_mae - v2_mae) / v1_mae * 100.0
        comparison[key] = {
            "v1_mae": round(v1_mae, 6) if v1_mae is not None else None,
            "v2_mae": round(v2_mae, 6),
            "v2_vs_v1_improvement_percent": round(delta, 2) if delta is not None else None,
            "new_in_v2": v1_mae is None,
        }

    artifact = {
        "pipeline_version": "prographer-context-model-v2.2",
        "model_type": "ExtraTreesRegressor",
        "random_state": 42,
        "feature_names": feature_names,
        "target_keys": list(models.keys()),
        "constant_profile_values": constant_profile_values,
        "learnability": learnability,
        "target_transforms": {
            key: ("reciprocal_temperature" if key == "temperature" else "identity")
            for key in models
        },
        "models": models,
    }
    model_path = model_dir / "context_model_v2.joblib"
    joblib.dump(artifact, model_path)

    result = {
        "pipeline_version": "prographer-context-model-v2.2",
        "model_type": "ExtraTreesRegressor",
        "model_path": str(model_path),
        "target_count": len(models),
        "target_keys": list(models.keys()),
        "constant_target_count": len(constant_profile_values),
        "constant_profile_values": constant_profile_values,
        "excluded_targets": {
            key: value
            for key, value in learnability.items()
            if value.get("status") != "trainable"
        },
        "train_samples": len(train),
        "validation_samples": len(validation),
        "test_samples": len(test),
        "validation": validation_metrics,
        "test": test_metrics,
        "v1_vs_v2": comparison,
        "test_opened_after_model_lock": True,
        "notes": {
            "experiment_design": "same model family as V1; Recipe Intelligence changes isolated",
            "temperature_target": "reciprocal temperature during training; reported back in Kelvin",
        },
    }

    (model_dir / "metrics_v2.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    emit("recipe_v2_training_completed", 100, result)
    return result
