from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.brain_v2.training.dataset_manifest import (
    build_dataset_manifest_from_readiness,
)
from tools.phase12_dataset_readiness import build_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument(
        "--preset-identity",
        default="none",
    )
    parser.add_argument(
        "--tone-curve-identity",
        default=None,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Dataset root not found: {root}")

    readiness = build_report(
        root=root,
        preset_identity=args.preset_identity,
        tone_curve_identity=args.tone_curve_identity,
        hash_raws=True,
    )
    manifest = build_dataset_manifest_from_readiness(readiness)

    output = (
        args.output.resolve()
        if args.output
        else Path.cwd().resolve().parent
        / "docs"
        / "runtime"
        / "phase12_dataset_manifest.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=== Phase 12 Dataset Import Manifest ===")
    print(f"dataset_id: {manifest.dataset_id}")
    print(f"samples: {manifest.sample_count}")
    print(f"training-ready: {manifest.training_ready_count}")
    print(f"events: {manifest.event_count}")
    print(f"usable events: {len(manifest.usable_event_ids)}")
    print(
        f"event-safe split ready: "
        f"{manifest.event_safe_split_ready}"
    )
    print(f"Manifest: {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
