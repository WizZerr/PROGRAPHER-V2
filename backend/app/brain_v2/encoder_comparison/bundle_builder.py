from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.brain_v2.components import RawInputRecord
from app.brain_v2.contracts import CameraInfo
from app.brain_v2.encoder_comparison.contracts import FeatureMatrix
from app.brain_v2.encoder_comparison.io import (
    save_dataset_npz,
    save_feature_npz,
)
from app.brain_v2.encoder_comparison.manifest_adapter import (
    ManifestSample,
    ManifestSelection,
)
from app.brain_v2.features import UnifiedFeatureExtractor
from app.brain_v2.preprocessing import RawPixelPreprocessor
from app.brain_v2.vision_encoders.hf_candidate import (
    HuggingFaceVisionEncoder,
)
from app.brain_v2.vision_encoders.registry import (
    CLIP_VIT_B32_ID,
    DINOV3_VITS16_ID,
    SIMPLE_MEASURED_ID,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if np.isfinite(numeric) else None


def _first_number(
    mapping: dict[str, Any],
    names: tuple[str, ...],
) -> float | None:
    for name in names:
        value = _number_or_none(mapping.get(name))
        if value is not None:
            return value
    return None


def _camera_info(sample: ManifestSample) -> CameraInfo:
    make = sample.camera.get("make")
    model = sample.camera.get("model")

    return CameraInfo(
        make=make.strip() if isinstance(make, str) and make.strip() else None,
        model=model.strip() if isinstance(model, str) and model.strip() else None,
    )


def _raw_wb(
    sample: ManifestSample,
) -> tuple[float, ...] | None:
    candidates = (
        sample.raw_info.get("raw_wb"),
        sample.exif.get("raw_wb"),
    )

    for value in candidates:
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            converted: list[float] = []
            valid = True
            for item in value:
                number = _number_or_none(item)
                if number is None:
                    valid = False
                    break
                converted.append(number)
            if valid:
                return tuple(converted)

    return None


def build_raw_input(
    sample: ManifestSample,
    source_path: Path,
) -> RawInputRecord:
    iso = _first_number(
        sample.exif,
        ("iso", "iso_speed"),
    )
    shutter = _first_number(
        sample.exif,
        ("shutter_seconds", "shutter_speed"),
    )
    aperture = _first_number(
        sample.exif,
        ("aperture", "f_number"),
    )
    focal = _first_number(
        sample.exif,
        ("focal_length_mm", "focal_length"),
    )
    wb = _raw_wb(sample)

    exif = {
        "iso": iso,
        "shutter_seconds": shutter,
        "aperture": aperture,
        "focal_length_mm": focal,
    }

    missing: list[str] = []
    camera = _camera_info(sample)

    if camera.model is None:
        missing.append("camera_model")
    if wb is None:
        missing.append("raw_wb")

    for field, value in exif.items():
        if value is None:
            missing.append(field)

    if not sample.capture_time:
        missing.append("captured_at")

    return RawInputRecord(
        source_fingerprint=_sha256_file(source_path),
        event_id=sample.event_group,
        camera=camera,
        captured_at=sample.capture_time,
        raw_wb=wb,
        exif=exif,
        missing_fields=tuple(missing),
        raw_path=str(source_path),
    )


@dataclass(frozen=True)
class BundleBuildResult:
    output_dir: Path
    dataset_path: Path
    measured_path: Path
    clip_path: Path | None
    dinov3_path: Path | None
    report_path: Path


def build_real_comparison_bundle(
    *,
    selection: ManifestSelection,
    output_dir: str | Path,
    device: str,
    include_clip: bool = True,
    include_dinov3: bool = False,
) -> BundleBuildResult:
    """
    All-or-nothing extraction.

    If any selected RAW cannot be decoded or encoded, no partial comparison
    matrix is accepted as a valid final bundle.
    """
    selection.validate()

    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)

    dataset_path = destination / "dataset.npz"
    measured_path = destination / "features_measured.npz"
    clip_path = (
        destination / "features_clip.npz"
        if include_clip
        else None
    )
    dinov3_path = (
        destination / "features_dinov3.npz"
        if include_dinov3
        else None
    )
    report_path = destination / "bundle_report.json"

    clip_encoder = None
    dino_encoder = None

    if include_clip:
        clip_encoder = HuggingFaceVisionEncoder(
            encoder_id=CLIP_VIT_B32_ID,
            device=device,
        )
        clip_encoder.load()

    if include_dinov3:
        dino_encoder = HuggingFaceVisionEncoder(
            encoder_id=DINOV3_VITS16_ID,
            device=device,
        )
        dino_encoder.load()

    measured_rows: list[np.ndarray] = []
    clip_rows: list[np.ndarray] = []
    dino_rows: list[np.ndarray] = []
    measured_version: str | None = None
    clip_version: str | None = None
    dino_version: str | None = None

    per_sample: list[dict[str, Any]] = []
    started = time.perf_counter()

    try:
        for index, sample in enumerate(selection.samples, start=1):
            source_path = Path(sample.source_path).expanduser().resolve(
                strict=True
            )
            sample_started = time.perf_counter()

            raw_input = build_raw_input(sample, source_path)
            preprocessed = RawPixelPreprocessor().run(raw_input)
            extracted = UnifiedFeatureExtractor().run(preprocessed)

            if measured_version is None:
                measured_version = extracted.features.version
            elif measured_version != extracted.features.version:
                raise RuntimeError(
                    "Measured feature version השתנתה בתוך bundle אחד."
                )

            measured_rows.append(
                np.asarray(
                    extracted.features.values,
                    dtype=np.float32,
                )
            )

            frame = preprocessed.decoded_frame
            if frame is None:
                raise RuntimeError(
                    f"{sample.sample_id}: decoded_frame חסר."
                )

            if clip_encoder is not None:
                clip = clip_encoder.encode(frame)
                clip_version = clip.encoder_version
                clip_rows.append(
                    np.asarray(clip.vector, dtype=np.float32)
                )

            if dino_encoder is not None:
                dino = dino_encoder.encode(frame)
                dino_version = dino.encoder_version
                dino_rows.append(
                    np.asarray(dino.vector, dtype=np.float32)
                )

            per_sample.append(
                {
                    "sample_id": sample.sample_id,
                    "source_path": str(source_path),
                    "split": sample.split,
                    "event_group": sample.event_group,
                    "seconds": time.perf_counter() - sample_started,
                }
            )

            print(
                f"[{index}/{selection.selected_total}] "
                f"{sample.sample_id} ✅"
            )

        sample_ids = selection.dataset.sample_ids

        measured_matrix = FeatureMatrix(
            candidate_id=SIMPLE_MEASURED_ID,
            feature_version=measured_version or "unknown",
            sample_ids=sample_ids,
            values=np.stack(measured_rows, axis=0),
        )
        measured_matrix.validate()

        clip_matrix = None
        if include_clip:
            clip_matrix = FeatureMatrix(
                candidate_id=CLIP_VIT_B32_ID,
                feature_version=clip_version or "unknown",
                sample_ids=sample_ids,
                values=np.stack(clip_rows, axis=0),
            )
            clip_matrix.validate()

        dino_matrix = None
        if include_dinov3:
            dino_matrix = FeatureMatrix(
                candidate_id=DINOV3_VITS16_ID,
                feature_version=dino_version or "unknown",
                sample_ids=sample_ids,
                values=np.stack(dino_rows, axis=0),
            )
            dino_matrix.validate()

        save_dataset_npz(dataset_path, selection.dataset)
        save_feature_npz(measured_path, measured_matrix)

        if clip_matrix is not None and clip_path is not None:
            save_feature_npz(clip_path, clip_matrix)

        if dino_matrix is not None and dinov3_path is not None:
            save_feature_npz(dinov3_path, dino_matrix)

        report = {
            "schema": "prographer.phase11.comparison-bundle.v1",
            "status": "complete",
            "manifest_total": selection.manifest_total,
            "selected_total": selection.selected_total,
            "excluded_test": selection.excluded_test,
            "device": device,
            "candidates": {
                "measured": {
                    "candidate_id": SIMPLE_MEASURED_ID,
                    "version": measured_version,
                    "dimension": int(measured_matrix.values.shape[1]),
                    "path": str(measured_path),
                },
                "clip": None
                if clip_matrix is None
                else {
                    "candidate_id": CLIP_VIT_B32_ID,
                    "version": clip_version,
                    "dimension": int(clip_matrix.values.shape[1]),
                    "path": str(clip_path),
                },
                "dinov3": None
                if dino_matrix is None
                else {
                    "candidate_id": DINOV3_VITS16_ID,
                    "version": dino_version,
                    "dimension": int(dino_matrix.values.shape[1]),
                    "path": str(dinov3_path),
                },
            },
            "dataset_path": str(dataset_path),
            "elapsed_seconds": time.perf_counter() - started,
            "samples": per_sample,
            "note": (
                "Test samples were excluded before extraction. "
                "No candidate ranking or promotion was performed."
            ),
        }

        report_path.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        return BundleBuildResult(
            output_dir=destination,
            dataset_path=dataset_path,
            measured_path=measured_path,
            clip_path=clip_path,
            dinov3_path=dinov3_path,
            report_path=report_path,
        )
    finally:
        if clip_encoder is not None:
            clip_encoder.unload()
        if dino_encoder is not None:
            dino_encoder.unload()
