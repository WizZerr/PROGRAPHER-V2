from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.brain_v2.components import RawInputRecord  # noqa: E402
from app.brain_v2.contracts import (  # noqa: E402
    Availability,
    BrainInput,
    CameraInfo,
)
from app.brain_v2.features import UnifiedFeatureExtractor  # noqa: E402
from app.brain_v2.preprocessing import RawPixelPreprocessor  # noqa: E402
from app.brain_v2.vision_encoders.benchmark import (  # noqa: E402
    benchmark_hf_encoder,
    vector_sha256,
)
from app.brain_v2.vision_encoders.registry import (  # noqa: E402
    CLIP_VIT_B32_ID,
    DINOV3_VITS16_ID,
    SIMPLE_MEASURED_ID,
)
from app.brain_v2.vision_encoders.runtime import detect_encoder_runtime  # noqa: E402
from app.brain_v2.vision_encoders.simple import SimpleMeasuredEncoder  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _build_input(raw_path: Path) -> tuple[BrainInput, object]:
    raw = RawInputRecord(
        source_fingerprint=_sha256(raw_path),
        event_id="phase11-real-encoder-benchmark",
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

    preprocessed = RawPixelPreprocessor().run(raw)
    extracted = UnifiedFeatureExtractor().run(preprocessed)
    source = preprocessed.source

    brain_input = BrainInput(
        source_fingerprint=source.source_fingerprint,
        event_id=source.event_id,
        camera=source.camera,
        captured_at=source.captured_at,
        raw_wb=source.raw_wb,
        exif=source.exif,
        missing_fields=source.missing_fields,
        preprocessing=preprocessed.preprocessing,
        features=extracted.features,
        scene_context=Availability(
            state="not_available",
            reason="Scene Context not implemented.",
        ),
        critic=Availability(
            state="not_available",
            reason="Critic not implemented.",
        ),
    )
    brain_input.validate()

    return brain_input, preprocessed.decoded_frame


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the same real RAW through measured/CLIP/DINOv3 encoders."
    )
    parser.add_argument("--raw", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda", "mps"),
        default="auto",
    )
    parser.add_argument(
        "--skip-dinov3",
        action="store_true",
        help="Run measured + CLIP only.",
    )
    parser.add_argument(
        "--output",
        default=str(
            BACKEND_ROOT.parent
            / "docs"
            / "runtime"
            / "phase11_real_encoder_benchmark.json"
        ),
    )
    parser.add_argument(
        "--vectors",
        default=str(
            BACKEND_ROOT.parent
            / "docs"
            / "runtime"
            / "phase11_real_encoder_vectors.npz"
        ),
    )
    args = parser.parse_args()

    if args.runs < 1:
        print("❌ --runs must be >= 1")
        return 2

    raw_path = Path(args.raw).expanduser().resolve(strict=True)
    runtime = detect_encoder_runtime()

    device = runtime.device if args.device == "auto" else args.device

    if device == "cuda" and not runtime.cuda_available:
        print("❌ CUDA requested but PyTorch does not expose CUDA.")
        return 3

    if device == "mps" and not runtime.mps_available:
        print("❌ MPS requested but PyTorch does not expose MPS.")
        return 4

    brain_input, frame = _build_input(raw_path)
    assert frame is not None

    measured_result = SimpleMeasuredEncoder().encode(brain_input)
    measured_vector = np.asarray(
        measured_result.vector,
        dtype=np.float32,
    )

    reports: list[dict] = [
        {
            "encoder_id": SIMPLE_MEASURED_ID,
            "status": "pass",
            "device": "cpu",
            "dimension": measured_result.dimension,
            "load_seconds": 0.0,
            "inference_seconds_median": None,
            "inference_seconds_min": None,
            "inference_seconds_max": None,
            "gpu_peak_allocated_mb": None,
            "gpu_peak_reserved_mb": None,
            "process_rss_before_mb": None,
            "process_rss_after_mb": None,
            "vector_l2_norm": float(np.linalg.norm(measured_vector)),
            "vector_sha256": vector_sha256(measured_result.vector),
            "error_type": None,
            "error_message": None,
        }
    ]

    vectors: dict[str, np.ndarray] = {
        "measured": measured_vector,
    }

    for encoder_id, key in (
        (CLIP_VIT_B32_ID, "clip"),
        (DINOV3_VITS16_ID, "dinov3"),
    ):
        if encoder_id == DINOV3_VITS16_ID and args.skip_dinov3:
            reports.append(
                {
                    "encoder_id": encoder_id,
                    "status": "skipped",
                    "device": device,
                    "dimension": None,
                    "error_type": None,
                    "error_message": "Skipped by --skip-dinov3.",
                }
            )
            continue

        print(f"Running {encoder_id} on {device} ...")
        report, vector = benchmark_hf_encoder(
            encoder_id=encoder_id,
            frame=frame,
            device=device,
            runs=args.runs,
        )
        reports.append(report.to_dict())

        if vector is not None:
            vectors[key] = np.asarray(vector, dtype=np.float32)

        if report.status == "pass":
            print(
                f"✅ {encoder_id}: dim={report.dimension}, "
                f"median={report.inference_seconds_median:.4f}s"
            )
        else:
            print(
                f"⚠️ {encoder_id}: {report.status} | "
                f"{report.error_type}: {report.error_message}"
            )

    payload = {
        "schema": "prographer.phase11.real-encoder-benchmark.v1",
        "raw_path": str(raw_path),
        "raw_sha256": _sha256(raw_path),
        "runs_per_pretrained_encoder": args.runs,
        "requested_device": args.device,
        "actual_device": device,
        "runtime": runtime.to_dict(),
        "brain_input": {
            "preprocessing_version": brain_input.preprocessing.version,
            "feature_version": brain_input.features.version,
            "measured_feature_count": len(brain_input.features.values),
            "raw_wb": list(brain_input.raw_wb) if brain_input.raw_wb else None,
            "missing_fields": list(brain_input.missing_fields),
        },
        "encoders": reports,
        "important_note": (
            "This is a runtime/embedding smoke benchmark only. "
            "It does not decide which encoder improves editing quality."
        ),
    }

    destination = Path(args.output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    vectors_path = Path(args.vectors).expanduser().resolve()
    vectors_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(vectors_path, **vectors)

    passed = [item for item in reports if item.get("status") == "pass"]
    blocked = [item for item in reports if item.get("status") == "blocked"]
    failed = [item for item in reports if item.get("status") == "failed"]

    print()
    print("=== Phase 11 encoder benchmark summary ===")
    print(f"Device: {device}")
    print(f"Passed: {len(passed)}")
    print(f"Blocked: {len(blocked)}")
    print(f"Failed: {len(failed)}")
    print(f"Report: {destination}")
    print(f"Vectors: {vectors_path}")

    if failed:
        return 5

    # Gated DINOv3 is a valid BLOCKED state until the user grants access.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
