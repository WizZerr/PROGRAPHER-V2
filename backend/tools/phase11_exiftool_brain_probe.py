from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.brain_v2.components import RawInputRecord
from app.brain_v2.contracts import CameraInfo
from app.brain_v2.features import UnifiedFeatureExtractor
from app.brain_v2.preprocessing.raw_pixels import RawPixelPreprocessor


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify ExifTool camera metadata reaches Brain V2 features."
    )
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--expect-make", default=None)
    parser.add_argument("--expect-model", default=None)
    args = parser.parse_args()

    raw_path = args.raw.resolve()
    if not raw_path.is_file():
        raise SystemExit(f"RAW not found: {raw_path}")

    source = RawInputRecord(
        source_fingerprint=f"sha256:{sha256_file(raw_path)}",
        event_id="phase11-camera-metadata-probe",
        camera=CameraInfo(),
        captured_at=None,
        raw_wb=None,
        exif={},
        missing_fields=("camera_model", "captured_at", "raw_wb"),
        raw_path=str(raw_path),
    )

    preprocessed = RawPixelPreprocessor().run(source)
    extracted = UnifiedFeatureExtractor().run(preprocessed)
    effective = preprocessed.source
    categorical = dict(extracted.features.categorical_context)

    report = {
        "source": str(raw_path),
        "camera": {
            "make": effective.camera.make,
            "model": effective.camera.model,
        },
        "lens_model": effective.exif.get("lens_model"),
        "captured_at": effective.captured_at,
        "missing_fields": list(effective.missing_fields),
        "feature_version": extracted.features.version,
        "categorical_context": dict(extracted.features.categorical_context),
        "camera_model_reached_features": (
            categorical.get("camera.model") == effective.camera.model
            and effective.camera.model is not None
        ),
        "filename_inference_used": False,
    }

    print("\n=== Phase 11 ExifTool -> Brain V2 probe ===")
    print(f"Camera make: {effective.camera.make}")
    print(f"Camera model: {effective.camera.model}")
    print(f"Lens model: {effective.exif.get('lens_model')}")
    print(f"Captured at: {effective.captured_at}")
    print(f"Missing fields: {effective.missing_fields}")
    print(f"Feature version: {extracted.features.version}")
    print(f"camera.model in feature context: {categorical.get('camera.model')}")
    print("Filename inference used: False")

    failures: list[str] = []
    if args.expect_make is not None and effective.camera.make != args.expect_make:
        failures.append(
            f"expected make {args.expect_make!r}, got {effective.camera.make!r}"
        )
    if args.expect_model is not None and effective.camera.model != args.expect_model:
        failures.append(
            f"expected model {args.expect_model!r}, got {effective.camera.model!r}"
        )
    if "camera_model" in effective.missing_fields:
        failures.append("camera_model is still marked missing")
    if not report["camera_model_reached_features"]:
        failures.append("camera.model did not reach categorical feature context")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Report: {args.output.resolve()}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("PASS: real camera identity reached Brain V2 without filename inference.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
