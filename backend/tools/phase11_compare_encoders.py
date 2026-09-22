from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.brain_v2.encoder_comparison.io import (
    load_dataset_npz,
    load_feature_npz,
    write_json,
)
from app.brain_v2.encoder_comparison.runner import (
    ComparisonConfig,
    compare_candidates,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--features", action="append", required=True)
    parser.add_argument(
        "--output",
        default=str(
            BACKEND_ROOT.parent
            / "docs"
            / "runtime"
            / "phase11_encoder_comparison.json"
        ),
    )
    args = parser.parse_args()

    dataset = load_dataset_npz(args.dataset)
    matrices = tuple(load_feature_npz(path) for path in args.features)

    report = compare_candidates(
        dataset=dataset,
        candidates=matrices,
        config=ComparisonConfig(),
    )
    write_json(args.output, report)

    print("✅ Phase 11 same-dataset encoder comparison complete")
    print(f"Train: {report['train_sample_count']}")
    print(f"Validation: {report['validation_sample_count']}")
    print(f"Candidates: {len(report['candidates'])}")

    for candidate in report["candidates"]:
        metrics = candidate["metrics"]["targets"]
        print()
        print(candidate["candidate_id"])
        print(f"  dimension: {candidate['feature_dimension']}")
        print(f"  Exposure MAE: {metrics['exposure_ev']['mae']:.6f} EV")
        print(f"  Temperature MAE: {metrics['temperature_k']['mae']:.2f} K")
        print(f"  Tint MAE: {metrics['tint']['mae']:.4f}")

    print()
    print("No candidate was automatically promoted or ranked.")
    print(f"Report: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
