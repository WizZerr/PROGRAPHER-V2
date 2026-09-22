from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.brain_v2.training.dataset_manifest import DatasetImportManifest
from app.brain_v2.training.event_split import build_event_safe_split


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--validation-fraction",
        type=float,
        default=0.20,
    )
    parser.add_argument(
        "--seed",
        default="phase12-v1",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"Dataset manifest not found: {manifest_path}")

    try:
        manifest = DatasetImportManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise SystemExit(
            f"Invalid dataset manifest: {type(exc).__name__}: {exc}"
        )

    split = build_event_safe_split(
        manifest,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
    )

    output = (
        args.output.resolve()
        if args.output
        else Path.cwd().resolve().parent
        / "docs"
        / "runtime"
        / "phase12_event_safe_split.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            split.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=== Phase 12 Event-Safe Split ===")
    print(f"dataset_id: {split.dataset_id}")
    print(f"split_id: {split.split_id}")
    print(f"seed: {split.seed}")
    print(f"validation fraction: {split.validation_fraction}")
    print(f"train events: {len(split.train_event_ids)}")
    print(f"validation events: {len(split.validation_event_ids)}")
    print(f"train samples: {split.train_sample_count}")
    print(f"validation samples: {split.validation_sample_count}")
    print(f"Split manifest: {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
