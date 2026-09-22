from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.brain_v2.vision_encoders.runtime import detect_encoder_runtime  # noqa: E402


def main() -> int:
    runtime = detect_encoder_runtime()

    print("=== ProGrapher Vision Runtime ===")
    print(f"Device: {runtime.device}")
    print(f"torch: {runtime.torch_version}")
    print(f"transformers: {runtime.transformers_version}")
    print(f"torchvision: {runtime.torchvision_version}")
    print(f"CUDA available: {runtime.cuda_available}")
    print(f"MPS available: {runtime.mps_available}")
    print(f"CUDA device: {runtime.cuda_device_name}")

    if runtime.torch_version is None:
        print("❌ torch is not installed")
        return 2

    if runtime.transformers_version is None:
        print("❌ transformers is not installed")
        return 3

    if sys.platform.startswith("win") and not runtime.cuda_available:
        print("❌ Windows reference machine did not expose CUDA to PyTorch")
        return 4

    print("✅ Vision runtime ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
