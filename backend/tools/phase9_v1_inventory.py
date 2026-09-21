from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation.legacy_inventory import write_inventory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory ProGrapher Legacy V1 artifacts for Phase 9"
    )
    parser.add_argument(
        "--legacy-root",
        required=True,
        help="Path to the bounded LEGACY folder to inspect.",
    )
    parser.add_argument(
        "--output",
        default=str(
            BACKEND_ROOT.parent
            / "docs"
            / "runtime"
            / "phase9_v1_inventory.json"
        ),
    )
    args = parser.parse_args()

    destination = write_inventory(
        args.legacy_root,
        args.output,
    )

    print("✅ Phase 9 V1 inventory created")
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
