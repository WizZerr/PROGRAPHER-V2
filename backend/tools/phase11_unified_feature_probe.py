from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.brain_v2.components import RawInputRecord  # noqa: E402
from app.brain_v2.contracts import CameraInfo  # noqa: E402
from app.brain_v2.factory import create_phase11_raw_pipeline  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ProGrapher Phase 11 unified Brain V2 feature probe"
    )
    parser.add_argument("--raw", required=True)
    parser.add_argument(
        "--output",
        default=str(
            BACKEND_ROOT.parent
            / "docs"
            / "runtime"
            / "phase11_unified_feature_probe.json"
        ),
    )
    args = parser.parse_args()

    raw_path = Path(args.raw).expanduser().resolve(strict=True)

    # Start from explicit unknowns. The RAW preprocessor is responsible for
    # recovering values it can prove directly from LibRaw/rawpy.
    raw_record = RawInputRecord(
        source_fingerprint=_sha256(raw_path),
        event_id="phase11-real-raw-probe",
        camera=CameraInfo(),
        captured_at=None,
        raw_wb=None,
        exif={
            "iso": None,
            "shutter_seconds": None,
            "aperture": None,
            "focal_length_mm": None,
        },
        missing_fields=(
            "camera_model",
            "raw_wb",
            "iso",
            "shutter_seconds",
            "aperture",
            "focal_length_mm",
            "captured_at",
        ),
        raw_path=str(raw_path),
    )

    result = create_phase11_raw_pipeline().run(
        raw_record
    )

    features = dict(
        zip(
            result.brain_input.features.feature_names,
            result.brain_input.features.values,
        )
    )

    recovered_exif = {
        key: result.brain_input.exif.get(key)
        for key in (
            "iso",
            "shutter_seconds",
            "aperture",
            "focal_length_mm",
        )
    }

    payload = {
        "schema": "prographer.phase11.unified-feature-probe.v2",
        "raw_path": str(raw_path),
        "preprocessing": {
            "version": result.brain_input.preprocessing.version,
            "raw_decoder": result.brain_input.preprocessing.raw_decoder,
            "color_pipeline": result.brain_input.preprocessing.color_pipeline,
        },
        "features": {
            "version": result.brain_input.features.version,
            "count": len(result.brain_input.features.values),
            "feature_names": list(
                result.brain_input.features.feature_names
            ),
            "values": list(
                result.brain_input.features.values
            ),
            "categorical_context": [
                list(item)
                for item in result.brain_input.features.categorical_context
            ],
        },
        "recovered_exif": recovered_exif,
        "raw_wb": (
            list(result.brain_input.raw_wb)
            if result.brain_input.raw_wb is not None
            else None
        ),
        "captured_at": result.brain_input.captured_at,
        "camera_matrix_available": (
            features.get("camera.rgb_xyz__missing") == 0.0
        ),
        "missing_fields": list(
            result.brain_input.missing_fields
        ),
        "quality": {
            "state": result.quality.availability.state,
            "requires_full_review": result.quality.requires_full_review,
            "confidence": result.quality.confidence,
        },
        "important_note": (
            "Camera make/model stay missing unless a reliable metadata "
            "provider supplies them. They are never inferred from filename."
        ),
    }

    destination = Path(args.output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print("✅ Phase 11 unified feature probe PASS")
    print(
        f"Preprocessing: "
        f"{result.brain_input.preprocessing.version}"
    )
    print(
        f"Features: "
        f"{result.brain_input.features.version}"
    )
    print(
        f"Numeric feature count: "
        f"{len(result.brain_input.features.values)}"
    )
    print(
        f"Recovered EXIF: {recovered_exif}"
    )
    print(
        f"RAW WB: {result.brain_input.raw_wb}"
    )
    print(
        f"Camera RGB->XYZ matrix available: "
        f"{payload['camera_matrix_available']}"
    )
    print(
        "Categorical camera identity: "
        f"{dict(result.brain_input.features.categorical_context)}"
    )
    print(
        f"Missing: {result.brain_input.missing_fields}"
    )
    print(
        "Quality confidence: "
        f"{result.quality.confidence}"
    )
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
