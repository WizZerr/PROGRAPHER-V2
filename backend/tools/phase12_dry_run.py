from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.brain_v2.training.dry_run import run_phase12_synthetic_dry_run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = run_phase12_synthetic_dry_run()

    output = (
        args.output.resolve()
        if args.output
        else Path.cwd().resolve().parent
        / "docs"
        / "runtime"
        / "phase12_end_to_end_dry_run.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=== Phase 12 End-to-End Synthetic Dry Run ===")
    print(f"schema: {report['schema_version']}")
    print(f"dataset_id: {report['manifest']['dataset_id']}")
    print(f"split_id: {report['split']['split_id']}")
    print(
        "samples: "
        f"{report['manifest']['sample_count']} total, "
        f"{report['split']['train_sample_count']} train, "
        f"{report['split']['validation_sample_count']} validation"
    )
    print(f"experiment_id: {report['experiment']['experiment_id']}")
    print(f"evaluation_id: {report['evaluation']['evaluation_id']}")
    print("pipeline assertions: PASS")
    print(
        "IMPORTANT: synthetic metrics are wiring evidence only; "
        "they are not a photographic-quality result."
    )
    print(f"Report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
