from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.brain_v2.encoder_comparison.bundle_builder import (  # noqa: E402
    build_real_comparison_bundle,
)
from app.brain_v2.encoder_comparison.manifest_adapter import (  # noqa: E402
    load_dataset_v2_manifest,
)
from app.brain_v2.vision_encoders.runtime import (  # noqa: E402
    detect_encoder_runtime,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a ProGrapher Dataset V2 manifest into a real "
            "same-dataset comparison bundle."
        )
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument(
        "--output-dir",
        default=str(
            BACKEND_ROOT.parent
            / "docs"
            / "runtime"
            / "phase11_comparison_bundle"
        ),
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda", "mps"),
        default="auto",
    )
    parser.add_argument(
        "--no-clip",
        action="store_true",
        help="Build measured features only.",
    )
    parser.add_argument(
        "--include-dinov3",
        action="store_true",
        help="Also extract DINOv3. Requires approved model access.",
    )
    args = parser.parse_args()

    runtime = detect_encoder_runtime()
    device = runtime.device if args.device == "auto" else args.device

    if device == "cuda" and not runtime.cuda_available:
        print("❌ CUDA requested but unavailable.")
        return 2
    if device == "mps" and not runtime.mps_available:
        print("❌ MPS requested but unavailable.")
        return 3

    selection = load_dataset_v2_manifest(args.manifest)

    print("=== Dataset V2 selection ===")
    print(f"Manifest samples: {selection.manifest_total}")
    print(f"Train/Validation selected: {selection.selected_total}")
    print(f"Test excluded and untouched: {selection.excluded_test}")
    print(f"Device: {device}")
    print()

    result = build_real_comparison_bundle(
        selection=selection,
        output_dir=args.output_dir,
        device=device,
        include_clip=not args.no_clip,
        include_dinov3=args.include_dinov3,
    )

    print()
    print("✅ Phase 11 comparison bundle complete")
    print(f"Dataset: {result.dataset_path}")
    print(f"Measured: {result.measured_path}")
    if result.clip_path:
        print(f"CLIP: {result.clip_path}")
    if result.dinov3_path:
        print(f"DINOv3: {result.dinov3_path}")
    print(f"Report: {result.report_path}")
    print()
    print("Next: run phase11_compare_encoders.py with these NPZ files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
