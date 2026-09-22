from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.brain_v2.vision_encoders.registry import encoder_registry  # noqa: E402
from app.brain_v2.vision_encoders.runtime import detect_encoder_runtime  # noqa: E402


def main() -> int:
    runtime = detect_encoder_runtime()
    candidates = encoder_registry()

    payload = {
        "schema": "prographer.phase11.encoder-inventory.v1",
        "runtime": runtime.to_dict(),
        "candidates": [item.to_dict() for item in candidates],
        "decision": (
            "No encoder is promoted by this inventory. "
            "Measured features remain the control candidate."
        ),
    }

    destination = (
        BACKEND_ROOT.parent
        / "docs"
        / "runtime"
        / "phase11_encoder_inventory.json"
    )
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

    print("✅ Phase 11 encoder inventory created")
    print(f"Runtime device: {runtime.device}")
    print(f"torch: {runtime.torch_version}")
    print(f"transformers: {runtime.transformers_version}")
    print(f"torchvision: {runtime.torchvision_version}")
    print(f"CUDA available: {runtime.cuda_available}")
    print(f"MPS available: {runtime.mps_available}")
    print(f"CUDA device: {runtime.cuda_device_name}")
    print()
    for item in candidates:
        print(
            f"- {item.encoder_id}: "
            f"{item.status} | {item.model_id or 'built-in'}"
        )
    print()
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
