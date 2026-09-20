from __future__ import annotations

import hashlib
import io
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

from PIL import Image, ImageOps

from .ai import BrainUnavailableError, get_brain
from .ai.prompts import PROMPT_GROUPS

try:
    import rawpy  # type: ignore
except Exception:
    rawpy = None

try:
    import exifread  # type: ignore
except Exception:
    exifread = None


ProgressFn = Callable[[str, int, dict[str, Any]], None]

TARGET_KEYS = [
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
]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        raise RuntimeError(f"Dataset file missing: {path.name}")
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip().lower().replace(",", "")
        text = text.replace("mm", "").replace("sec", "").strip()
        if text.startswith("f/"):
            text = text[2:]
        if "/" in text and all(part.strip().replace(".", "", 1).isdigit() for part in text.split("/", 1)):
            a, b = text.split("/", 1)
            bval = float(b)
            return float(a) / bval if bval else default
        return float(text)
    except Exception:
        return default


def _tag_text(tags: dict, *names: str) -> Optional[str]:
    for name in names:
        if name in tags:
            text = str(tags[name]).strip()
            if text:
                return text
    return None


def extract_training_metadata(path: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "iso": 0.0,
        "aperture": 0.0,
        "shutter_seconds": 0.0,
        "focal_length": 0.0,
        "width": 0.0,
        "height": 0.0,
        "camera_make": "",
        "camera_model": "",
        "lens": "",
    }

    if exifread is not None:
        try:
            with path.open("rb") as handle:
                tags = exifread.process_file(handle, details=False, strict=False)
            metadata["iso"] = _safe_float(_tag_text(tags, "EXIF ISOSpeedRatings", "Image ISOSpeedRatings"), 0.0)
            metadata["aperture"] = _safe_float(_tag_text(tags, "EXIF FNumber"), 0.0)
            metadata["shutter_seconds"] = _safe_float(_tag_text(tags, "EXIF ExposureTime"), 0.0)
            metadata["focal_length"] = _safe_float(_tag_text(tags, "EXIF FocalLength"), 0.0)
            metadata["camera_make"] = _tag_text(tags, "Image Make") or ""
            metadata["camera_model"] = _tag_text(tags, "Image Model") or ""
            metadata["lens"] = _tag_text(tags, "EXIF LensModel", "EXIF LensSpecification") or ""
            metadata["width"] = _safe_float(_tag_text(tags, "EXIF ExifImageWidth", "Image ImageWidth"), 0.0)
            metadata["height"] = _safe_float(_tag_text(tags, "EXIF ExifImageLength", "Image ImageLength"), 0.0)
        except Exception:
            pass

    return metadata


def _raw_preview(path: Path) -> Image.Image:
    if rawpy is None:
        raise RuntimeError("rawpy is required for RAW Vision preprocessing. Run install_raw_support.bat.")

    with rawpy.imread(str(path)) as raw:
        try:
            thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                image = Image.open(io.BytesIO(thumb.data))
                image.load()
                return image.convert("RGB")
            if thumb.format == rawpy.ThumbFormat.BITMAP:
                return Image.fromarray(thumb.data).convert("RGB")
        except Exception:
            pass

        rgb = raw.postprocess(
            use_camera_wb=True,
            no_auto_bright=False,
            half_size=True,
            output_bps=8,
        )
        return Image.fromarray(rgb).convert("RGB")


def load_vision_image(path: Path) -> Image.Image:
    suffix = path.suffix.lower()
    if suffix in {".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".raf", ".pef"}:
        image = _raw_preview(path)
    else:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
    image.thumbnail((1280, 1280))
    return image


def _done_sample_ids(output_dir: Path) -> set[str]:
    done: set[str] = set()
    for split in ("train", "validation", "test"):
        path = output_dir / f"{split}.jsonl"
        if not path.exists():
            continue
        try:
            for row in _read_jsonl(path):
                sid = str(row.get("sample_id") or "")
                if sid:
                    done.add(sid)
        except Exception:
            continue
    return done


def build_vision_features(
    dataset_dir: Path,
    output_dir: Path,
    progress: Optional[ProgressFn] = None,
    batch_size: int = 8,
) -> dict[str, Any]:
    dataset_dir = Path(dataset_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    split_rows = {
        "train": _read_jsonl(dataset_dir / "train.jsonl"),
        "validation": _read_jsonl(dataset_dir / "validation.jsonl"),
        "test": _read_jsonl(dataset_dir / "test.jsonl"),
    }
    ordered: list[tuple[str, dict[str, Any]]] = []
    for split in ("train", "validation", "test"):
        ordered.extend((split, row) for row in split_rows[split])

    total = len(ordered)
    if not total:
        raise RuntimeError("Dataset contains no samples for Vision analysis.")

    done = _done_sample_ids(output_dir)

    def emit(stage: str, pct: int, details: dict[str, Any]):
        if progress:
            progress(stage, pct, details)

    # Report real startup work before CLIP warmup. Loading the local model can
    # take noticeable time on first use, so the UI must not sit at "queued 1%".
    emit("warming_vision", 2, {
        "total": total,
        "processed": len(done),
        "device": None,
        "model_name": None,
        "message": "Loading local Vision model",
    })

    brain = get_brain()
    warm = brain.warmup()
    started = time.monotonic()

    emit("warming_vision", 3, {
        "total": total,
        "processed": len(done),
        "device": warm.get("device"),
        "model_name": warm.get("model_name"),
        "message": "Vision model ready",
    })

    batch_images: list[Image.Image] = []
    batch_records: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    processed = len(done)
    failed = 0
    split_processed = {"train": 0, "validation": 0, "test": 0}

    # Restore counters for resumable jobs.
    for split in ("train", "validation", "test"):
        out_path = output_dir / f"{split}.jsonl"
        if out_path.exists():
            try:
                split_processed[split] = len(_read_jsonl(out_path))
            except Exception:
                split_processed[split] = 0

    def flush_batch():
        nonlocal batch_images, batch_records, processed, failed
        if not batch_images:
            return

        results = brain.analyze_images(batch_images)
        for (split, sample, metadata), result in zip(batch_records, results):
            enriched = {
                "sample_id": sample.get("sample_id"),
                "split": split,
                "filename": sample.get("filename"),
                "source_path": sample.get("source_path"),
                "source_file_id": sample.get("source_file_id"),
                "lightroom_image_id": sample.get("lightroom_image_id"),
                "target_style": sample.get("target_style") or {},
                "metadata": metadata,
                "embedding": result.get("embedding") or [],
                "semantics": {
                    "groups": result.get("groups") or {},
                    "top": result.get("top") or {},
                },
                "vision_model": result.get("model_name"),
                "vision_device": result.get("device"),
                "develop_recipe": sample.get("develop_recipe") or {},
                "test_locked": split == "test",
            }
            _append_jsonl(output_dir / f"{split}.jsonl", enriched)
            processed += 1
            split_processed[split] += 1

        elapsed = max(0.001, time.monotonic() - started)
        speed = processed / elapsed
        remaining = max(0, total - processed)
        eta_seconds = int(remaining / speed) if speed > 0 else None
        pct = 3 + int((processed / total) * 95)
        emit("vision_processing", min(98, pct), {
            "processed": processed,
            "total": total,
            "failed": failed,
            "train_processed": split_processed["train"],
            "validation_processed": split_processed["validation"],
            "test_processed": split_processed["test"],
            "images_per_second": round(speed, 3),
            "eta_seconds": eta_seconds,
            "device": warm.get("device"),
            "model_name": warm.get("model_name"),
        })
        batch_images = []
        batch_records = []

    for split, sample in ordered:
        sid = str(sample.get("sample_id") or "")
        if sid and sid in done:
            continue

        source = Path(str(sample.get("source_path") or ""))
        if not source.exists():
            failed += 1
            continue

        try:
            image = load_vision_image(source)
            metadata = extract_training_metadata(source)
            batch_images.append(image)
            batch_records.append((split, sample, metadata))
            if len(batch_images) >= max(1, batch_size):
                flush_batch()
        except BrainUnavailableError:
            raise
        except Exception:
            failed += 1

    flush_batch()

    if processed != total:
        raise RuntimeError(
            f"Vision preprocessing incomplete: {processed}/{total} samples succeeded; {failed} failed."
        )

    manifest = {
        "pipeline_version": "prographer-profile-vision-v1",
        "model_name": warm.get("model_name"),
        "device": warm.get("device"),
        "embedding_dimensions": warm.get("embedding_dimensions"),
        "total": total,
        "processed": processed,
        "failed": failed,
        "splits": {
            "train": split_processed["train"],
            "validation": split_processed["validation"],
            "test": split_processed["test"],
        },
        "test_locked": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    emit("vision_completed", 100, manifest)
    return manifest


def _semantic_feature_layout() -> list[tuple[str, str]]:
    layout: list[tuple[str, str]] = []
    for group_name, entries in PROMPT_GROUPS.items():
        for key, _label, _prompt in entries:
            layout.append((group_name, key))
    return layout


SEMANTIC_LAYOUT = _semantic_feature_layout()


def _feature_vector(record: dict[str, Any]) -> tuple[list[str], list[float]]:
    embedding = [float(x) for x in (record.get("embedding") or [])]
    metadata = record.get("metadata") or {}

    iso = max(0.0, _safe_float(metadata.get("iso"), 0.0))
    aperture = max(0.0, _safe_float(metadata.get("aperture"), 0.0))
    shutter = max(0.0, _safe_float(metadata.get("shutter_seconds"), 0.0))
    focal = max(0.0, _safe_float(metadata.get("focal_length"), 0.0))
    width = max(0.0, _safe_float(metadata.get("width"), 0.0))
    height = max(0.0, _safe_float(metadata.get("height"), 0.0))

    meta_names = [
        "meta_log_iso",
        "meta_aperture",
        "meta_log_shutter",
        "meta_focal_length",
        "meta_aspect_ratio",
        "meta_log_pixels",
    ]
    meta_values = [
        math.log1p(iso),
        aperture,
        math.log1p(shutter),
        focal,
        (width / height) if height else 0.0,
        math.log1p(width * height) if width and height else 0.0,
    ]

    groups = ((record.get("semantics") or {}).get("groups") or {})
    semantic_names: list[str] = []
    semantic_values: list[float] = []
    score_maps: dict[str, dict[str, float]] = {}
    for group_name, candidates in groups.items():
        score_maps[group_name] = {
            str(item.get("key") or ""): float(item.get("score_percent") or 0.0) / 100.0
            for item in (candidates or [])
        }

    for group_name, key in SEMANTIC_LAYOUT:
        semantic_names.append(f"semantic__{group_name}__{key}")
        semantic_values.append(score_maps.get(group_name, {}).get(key, 0.0))

    names = [f"embed_{i}" for i in range(len(embedding))] + meta_names + semantic_names
    values = embedding + meta_values + semantic_values
    return names, values


def train_context_model(
    vision_dir: Path,
    model_dir: Path,
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

    vision_dir = Path(vision_dir)
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    train = _read_jsonl(vision_dir / "train.jsonl")
    validation = _read_jsonl(vision_dir / "validation.jsonl")
    test = _read_jsonl(vision_dir / "test.jsonl")
    if not train or not validation or not test:
        raise RuntimeError("Vision feature splits are incomplete.")

    def emit(stage: str, pct: int, details: dict[str, Any]):
        if progress:
            progress(stage, pct, details)

    emit("loading_features", 3, {
        "train": len(train),
        "validation": len(validation),
        "test": len(test),
    })

    first_names, _ = _feature_vector(train[0])
    feature_names = first_names

    X_train_all = np.asarray([_feature_vector(row)[1] for row in train], dtype=np.float32)
    X_val_all = np.asarray([_feature_vector(row)[1] for row in validation], dtype=np.float32)
    X_test_all = np.asarray([_feature_vector(row)[1] for row in test], dtype=np.float32)

    models: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    eligible_keys = []

    # Only train controls that genuinely exist in enough Expert-C targets.
    for key in TARGET_KEYS:
        coverage = sum(1 for row in train if key in (row.get("develop_recipe") or {})) / max(1, len(train))
        if coverage >= 0.50:
            eligible_keys.append(key)

    if not eligible_keys:
        raise RuntimeError("No Lightroom target controls have enough coverage for training.")

    for index, key in enumerate(eligible_keys):
        train_idx = [i for i, row in enumerate(train) if key in (row.get("develop_recipe") or {})]
        val_idx = [i for i, row in enumerate(validation) if key in (row.get("develop_recipe") or {})]
        test_idx = [i for i, row in enumerate(test) if key in (row.get("develop_recipe") or {})]
        if len(train_idx) < 100 or len(val_idx) < 20:
            continue

        y_train = np.asarray([float(train[i]["develop_recipe"][key]) for i in train_idx], dtype=np.float32)
        y_val = np.asarray([float(validation[i]["develop_recipe"][key]) for i in val_idx], dtype=np.float32)

        model = ExtraTreesRegressor(
            n_estimators=192,
            random_state=42,
            n_jobs=-1,
            min_samples_leaf=2,
            max_features=0.80,
        )
        model.fit(X_train_all[train_idx], y_train)
        val_pred = model.predict(X_val_all[val_idx])
        val_mae = float(mean_absolute_error(y_val, val_pred))
        baseline_value = float(np.median(y_train))
        baseline_pred = np.full_like(y_val, baseline_value)
        baseline_mae = float(mean_absolute_error(y_val, baseline_pred))
        improvement = (
            (baseline_mae - val_mae) / baseline_mae * 100.0
            if baseline_mae > 1e-9 else 0.0
        )

        models[key] = model
        metrics[key] = {
            "train_samples": len(train_idx),
            "validation_samples": len(val_idx),
            "test_samples": len(test_idx),
            "validation_mae": round(val_mae, 6),
            "validation_baseline_mae": round(baseline_mae, 6),
            "validation_improvement_percent": round(improvement, 2),
            "target_median": round(baseline_value, 6),
        }

        pct = 8 + int(((index + 1) / max(1, len(eligible_keys))) * 60)
        emit("training_models", min(68, pct), {
            "parameter": key,
            "parameter_index": index + 1,
            "parameter_total": len(eligible_keys),
            "trained_parameters": len(models),
        })

    if not models:
        raise RuntimeError("No parameter model could be trained from the Dataset.")

    # Model selection is complete at this point. Test is opened only now.
    emit("locking_model", 72, {"trained_parameters": len(models)})

    test_metrics: dict[str, Any] = {}
    for index, (key, model) in enumerate(models.items()):
        test_idx = [i for i, row in enumerate(test) if key in (row.get("develop_recipe") or {})]
        if not test_idx:
            continue
        y_test = np.asarray([float(test[i]["develop_recipe"][key]) for i in test_idx], dtype=np.float32)
        pred = model.predict(X_test_all[test_idx])
        mae = float(mean_absolute_error(y_test, pred))
        baseline_value = float(metrics[key]["target_median"])
        baseline_mae = float(mean_absolute_error(y_test, np.full_like(y_test, baseline_value)))
        improvement = (
            (baseline_mae - mae) / baseline_mae * 100.0
            if baseline_mae > 1e-9 else 0.0
        )
        test_metrics[key] = {
            "samples": len(test_idx),
            "mae": round(mae, 6),
            "baseline_mae": round(baseline_mae, 6),
            "improvement_percent": round(improvement, 2),
        }
        emit("testing_locked_set", 74 + int(((index + 1) / len(models)) * 20), {
            "parameter": key,
            "tested_parameters": index + 1,
            "parameter_total": len(models),
        })

    artifact = {
        "pipeline_version": "prographer-context-model-v1",
        "model_type": "ExtraTreesRegressor",
        "random_state": 42,
        "feature_names": feature_names,
        "semantic_layout": SEMANTIC_LAYOUT,
        "target_keys": list(models.keys()),
        "models": models,
    }
    model_path = model_dir / "context_model_v1.joblib"
    joblib.dump(artifact, model_path)

    result = {
        "pipeline_version": "prographer-context-model-v1",
        "model_type": "ExtraTreesRegressor",
        "model_path": str(model_path),
        "feature_count": len(feature_names),
        "target_count": len(models),
        "target_keys": list(models.keys()),
        "train_samples": len(train),
        "validation_samples": len(validation),
        "test_samples": len(test),
        "validation": metrics,
        "test": test_metrics,
        "test_opened_after_model_lock": True,
        "notes": {
            "gpu_usage": "CLIP Vision runs on CUDA when available. ExtraTrees training runs on CPU.",
            "status": "experimental_context_baseline",
        },
    }
    (model_dir / "metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    emit("training_completed", 100, result)
    return result


def evaluate_context_model(
    vision_dir: Path,
    model_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """
    Deep evaluation of a locked model on the TEST split only.

    This function never fits or updates a model. It loads the already-saved
    artifact, opens only `test.jsonl`, generates predictions, and writes an
    analysis artifact that can be inspected by the UI.
    """
    try:
        import joblib  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Evaluation dependencies are missing. Run install_training_lab.bat first."
        ) from exc

    vision_dir = Path(vision_dir)
    model_path = Path(model_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not model_path.exists():
        raise RuntimeError("Saved model artifact was not found.")

    artifact = joblib.load(model_path)
    models = artifact.get("models") or {}
    target_keys = list(artifact.get("target_keys") or models.keys())
    if not models:
        raise RuntimeError("Saved model artifact contains no trained parameter models.")

    train = _read_jsonl(vision_dir / "train.jsonl")
    validation = _read_jsonl(vision_dir / "validation.jsonl")
    test = _read_jsonl(vision_dir / "test.jsonl")
    if not test:
        raise RuntimeError("TEST split is empty.")

    X_test = np.asarray(
        [_feature_vector(row)[1] for row in test],
        dtype=np.float32,
    )

    # Coverage explains why a parameter was or was not eligible for V1.
    coverage: dict[str, Any] = {}
    for key in TARGET_KEYS:
        train_count = sum(1 for row in train if key in (row.get("develop_recipe") or {}))
        val_count = sum(1 for row in validation if key in (row.get("develop_recipe") or {}))
        test_count = sum(1 for row in test if key in (row.get("develop_recipe") or {}))
        train_ratio = train_count / max(1, len(train))
        trained = key in models

        if trained:
            reason = "trained"
        elif train_ratio < 0.50:
            reason = "insufficient_target_coverage"
        elif train_count < 100 or val_count < 20:
            reason = "insufficient_split_samples"
        else:
            reason = "not_selected_by_v1"

        coverage[key] = {
            "trained": trained,
            "reason": reason,
            "train_count": train_count,
            "train_total": len(train),
            "train_coverage_percent": round(train_ratio * 100.0, 2),
            "validation_count": val_count,
            "validation_total": len(validation),
            "test_count": test_count,
            "test_total": len(test),
        }

    parameter_stats: dict[str, Any] = {}
    sample_rows: list[dict[str, Any]] = []

    predictions_by_key: dict[str, Any] = {}
    for key in target_keys:
        model = models.get(key)
        if model is None:
            continue
        predictions_by_key[key] = model.predict(X_test)

    # Per-parameter statistics and baseline comparison.
    baseline_mae_by_key: dict[str, float] = {}
    for key in target_keys:
        model = models.get(key)
        if model is None:
            continue

        idx = [i for i, row in enumerate(test) if key in (row.get("develop_recipe") or {})]
        if not idx:
            continue

        actual = np.asarray(
            [float(test[i]["develop_recipe"][key]) for i in idx],
            dtype=np.float32,
        )
        predicted = np.asarray(
            [float(predictions_by_key[key][i]) for i in idx],
            dtype=np.float32,
        )
        abs_error = np.abs(actual - predicted)

        train_values = [
            float(row["develop_recipe"][key])
            for row in train
            if key in (row.get("develop_recipe") or {})
        ]
        baseline_value = float(np.median(np.asarray(train_values, dtype=np.float32)))
        baseline_abs = np.abs(actual - baseline_value)
        baseline_mae = float(np.mean(baseline_abs))
        baseline_mae_by_key[key] = baseline_mae

        mae = float(np.mean(abs_error))
        improvement = (
            (baseline_mae - mae) / baseline_mae * 100.0
            if baseline_mae > 1e-9 else 0.0
        )

        parameter_stats[key] = {
            "samples": len(idx),
            "mae": round(mae, 6),
            "median_abs_error": round(float(np.median(abs_error)), 6),
            "p90_abs_error": round(float(np.percentile(abs_error, 90)), 6),
            "p95_abs_error": round(float(np.percentile(abs_error, 95)), 6),
            "max_abs_error": round(float(np.max(abs_error)), 6),
            "baseline_value": round(baseline_value, 6),
            "baseline_mae": round(baseline_mae, 6),
            "improvement_percent": round(improvement, 2),
        }

    # Per-image predictions. Composite error is normalized by the parameter's
    # baseline MAE, making parameters with different units comparable.
    for i, row in enumerate(test):
        params: dict[str, Any] = {}
        normalized_errors: list[float] = []

        for key in target_keys:
            recipe = row.get("develop_recipe") or {}
            if key not in recipe or key not in predictions_by_key:
                continue

            actual = float(recipe[key])
            predicted = float(predictions_by_key[key][i])
            error = abs(actual - predicted)
            baseline_scale = max(1e-9, baseline_mae_by_key.get(key, 1.0))
            normalized = error / baseline_scale
            normalized_errors.append(normalized)

            params[key] = {
                "actual": round(actual, 6),
                "predicted": round(predicted, 6),
                "abs_error": round(error, 6),
                "normalized_error": round(normalized, 6),
            }

        composite = (
            float(sum(normalized_errors) / len(normalized_errors))
            if normalized_errors else 0.0
        )

        metadata = row.get("metadata") or {}
        semantics = row.get("semantics") or {}
        top_semantics = (semantics.get("top") or {})

        sample_rows.append({
            "sample_id": row.get("sample_id"),
            "filename": row.get("filename"),
            "source_path": row.get("source_path"),
            "split": "test",
            "target_style": row.get("target_style") or {},
            "composite_normalized_error": round(composite, 6),
            "parameters": params,
            "metadata": {
                "iso": metadata.get("iso"),
                "aperture": metadata.get("aperture"),
                "shutter_seconds": metadata.get("shutter_seconds"),
                "focal_length": metadata.get("focal_length"),
                "camera_model": metadata.get("camera_model"),
                "lens": metadata.get("lens"),
            },
            "vision_top": top_semantics,
        })

    sample_rows.sort(key=lambda x: x["composite_normalized_error"])
    best = sample_rows[:12]
    worst = list(reversed(sample_rows[-12:]))

    # Deterministic representative sample spread through the ordered TEST set.
    representative: list[dict[str, Any]] = []
    if sample_rows:
        count = min(12, len(sample_rows))
        for n in range(count):
            pos = int(round(n * (len(sample_rows) - 1) / max(1, count - 1)))
            representative.append(sample_rows[pos])

    composite_values = np.asarray(
        [row["composite_normalized_error"] for row in sample_rows],
        dtype=np.float32,
    )
    parameter_improvements = [
        float(stats["improvement_percent"])
        for stats in parameter_stats.values()
    ]

    # Aggregate feature importance into interpretable groups.
    feature_names = list(artifact.get("feature_names") or [])
    aggregate_importance = [0.0 for _ in feature_names]
    model_count = 0
    for model in models.values():
        importance = getattr(model, "feature_importances_", None)
        if importance is None or len(importance) != len(feature_names):
            continue
        model_count += 1
        for idx, value in enumerate(importance):
            aggregate_importance[idx] += float(value)

    if model_count:
        aggregate_importance = [v / model_count for v in aggregate_importance]

    feature_pairs = sorted(
        zip(feature_names, aggregate_importance),
        key=lambda item: item[1],
        reverse=True,
    )
    top_features = [
        {"name": name, "importance": round(value, 8)}
        for name, value in feature_pairs[:20]
    ]

    groups = {"embedding": 0.0, "metadata": 0.0, "semantic": 0.0}
    for name, value in feature_pairs:
        if name.startswith("embed_"):
            groups["embedding"] += value
        elif name.startswith("meta_"):
            groups["metadata"] += value
        elif name.startswith("semantic__"):
            groups["semantic"] += value

    group_total = sum(groups.values()) or 1.0
    feature_group_importance = {
        key: round(value / group_total * 100.0, 2)
        for key, value in groups.items()
    }

    result = {
        "evaluation_version": "prographer-evaluation-v1",
        "model_type": artifact.get("model_type") or "Unknown",
        "model_path": str(model_path),
        "test_samples": len(test),
        "trained_parameter_count": len(parameter_stats),
        "trained_parameters": list(parameter_stats.keys()),
        "parameter_stats": parameter_stats,
        "coverage": coverage,
        "overall": {
            "mean_parameter_improvement_percent": round(
                sum(parameter_improvements) / max(1, len(parameter_improvements)),
                2,
            ),
            "median_composite_normalized_error": round(
                float(np.median(composite_values)), 6
            ) if len(composite_values) else 0.0,
            "p90_composite_normalized_error": round(
                float(np.percentile(composite_values, 90)), 6
            ) if len(composite_values) else 0.0,
            "test_was_locked": True,
        },
        "feature_group_importance_percent": feature_group_importance,
        "top_features": top_features,
        "best_samples": best,
        "worst_samples": worst,
        "representative_samples": representative,
        "samples": sample_rows,
    }

    (output_dir / "evaluation_v1.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result

