from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.brain_v2.training.lightroom_targets import (
    LightroomTargetExtractionError,
    extract_phase12_target_sample_from_xmp,
)

RAW_EXTENSIONS = {
    ".3fr", ".arw", ".cr2", ".cr3", ".dng", ".erf", ".iiq", ".kdc",
    ".mos", ".mrw", ".nef", ".nrw", ".orf", ".pef", ".raf", ".raw",
    ".rw2", ".srw",
}


@dataclass(frozen=True)
class PairRecord:
    event_id: str
    raw_path: Path
    xmp_path: Path | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_kind(path: Path) -> str:
    return "dng_raw" if path.suffix.lower() == ".dng" else "camera_raw"


def _event_directories(root: Path) -> list[Path]:
    child_dirs = sorted(
        (path for path in root.iterdir() if path.is_dir()),
        key=lambda path: path.name.lower(),
    )
    if child_dirs:
        return child_dirs
    return [root]


def _collect_pairs(event_dir: Path, event_id: str) -> list[PairRecord]:
    raws = sorted(
        (
            path
            for path in event_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in RAW_EXTENSIONS
        ),
        key=lambda path: str(path).lower(),
    )

    return [
        PairRecord(
            event_id=event_id,
            raw_path=raw,
            xmp_path=raw.with_suffix(raw.suffix + ".xmp")
            if raw.with_suffix(raw.suffix + ".xmp").is_file()
            else (
                raw.with_suffix(".xmp")
                if raw.with_suffix(".xmp").is_file()
                else None
            ),
        )
        for raw in raws
    ]


def _analyze_pair(
    pair: PairRecord,
    *,
    preset_identity: str,
    tone_curve_identity: str | None,
    hash_raws: bool,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "event_id": pair.event_id,
        "raw_path": str(pair.raw_path),
        "raw_name": pair.raw_path.name,
        "raw_extension": pair.raw_path.suffix.lower(),
        "xmp_path": str(pair.xmp_path) if pair.xmp_path else None,
        "pair_status": "paired" if pair.xmp_path else "missing_xmp",
        "target_status": "not_checked",
        "ready_for_three_target_training": False,
        "missing_target_fields": [],
        "rendering_context": None,
        "error": None,
    }

    if hash_raws:
        row["raw_sha256"] = _sha256(pair.raw_path)

    if pair.xmp_path is None:
        row["target_status"] = "missing_xmp"
        return row

    try:
        extraction = extract_phase12_target_sample_from_xmp(
            xmp_path=pair.xmp_path,
            source_kind=_source_kind(pair.raw_path),
            preset_identity=preset_identity,
            tone_curve_identity=tone_curve_identity,
        )
    except LightroomTargetExtractionError as exc:
        row["target_status"] = "invalid_xmp_or_context"
        row["error"] = str(exc)
        return row
    except Exception as exc:
        row["target_status"] = "unexpected_error"
        row["error"] = f"{type(exc).__name__}: {exc}"
        return row

    sample = extraction.sample
    row["target_status"] = (
        "ready"
        if sample.ready_for_three_target_training
        else "missing_targets"
    )
    row["ready_for_three_target_training"] = (
        sample.ready_for_three_target_training
    )
    row["missing_target_fields"] = list(
        extraction.missing_target_fields
    )
    row["targets"] = {
        "exposure_stops": sample.targets.exposure_stops,
        "temperature_k": sample.targets.temperature_k,
        "tint": sample.targets.tint,
    }
    row["rendering_context"] = {
        "process_version": sample.rendering_context.process_version,
        "camera_profile": sample.rendering_context.camera_profile,
        "tone_curve": sample.rendering_context.tone_curve,
        "preset_identity": sample.rendering_context.preset_identity,
        "white_balance_mode": sample.rendering_context.white_balance_mode,
    }
    return row


def _duplicate_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        digest = row.get("raw_sha256")
        if not digest:
            continue
        by_hash.setdefault(digest, []).append(row)

    groups = []
    for digest, items in by_hash.items():
        if len(items) < 2:
            continue
        groups.append(
            {
                "sha256": digest,
                "count": len(items),
                "paths": [item["raw_path"] for item in items],
                "event_ids": sorted({item["event_id"] for item in items}),
            }
        )
    return groups


def build_report(
    *,
    root: Path,
    preset_identity: str,
    tone_curve_identity: str | None,
    hash_raws: bool,
) -> dict[str, Any]:
    events = _event_directories(root)

    rows: list[dict[str, Any]] = []
    event_summaries: list[dict[str, Any]] = []

    for event_dir in events:
        event_id = event_dir.name if event_dir != root else root.name
        pairs = _collect_pairs(event_dir, event_id)
        event_rows = [
            _analyze_pair(
                pair,
                preset_identity=preset_identity,
                tone_curve_identity=tone_curve_identity,
                hash_raws=hash_raws,
            )
            for pair in pairs
        ]
        rows.extend(event_rows)

        event_summaries.append(
            {
                "event_id": event_id,
                "event_path": str(event_dir),
                "raw_count": len(event_rows),
                "paired_xmp_count": sum(
                    1 for row in event_rows
                    if row["pair_status"] == "paired"
                ),
                "training_ready_count": sum(
                    1 for row in event_rows
                    if row["ready_for_three_target_training"]
                ),
            }
        )

    ready = [
        row for row in rows
        if row["ready_for_three_target_training"]
    ]
    missing_xmp = [
        row for row in rows
        if row["pair_status"] == "missing_xmp"
    ]
    invalid = [
        row for row in rows
        if row["target_status"] in {
            "invalid_xmp_or_context",
            "unexpected_error",
        }
    ]
    missing_targets = [
        row for row in rows
        if row["target_status"] == "missing_targets"
    ]
    duplicates = _duplicate_groups(rows) if hash_raws else []

    usable_event_ids = sorted({
        row["event_id"]
        for row in ready
    })

    event_safe_split_ready = len(usable_event_ids) >= 2

    return {
        "schema_version": "phase12-dataset-readiness-v1",
        "root": str(root),
        "assumptions": {
            "event_layout": (
                "each immediate child directory is treated as one event; "
                "if there are no child directories, the root itself is one event"
            ),
            "xmp_pairing": (
                "RAW.ext.xmp is preferred, then RAW-stem.xmp"
            ),
            "preset_identity": preset_identity,
            "tone_curve_override": tone_curve_identity,
        },
        "summary": {
            "event_count": len(events),
            "raw_count": len(rows),
            "paired_xmp_count": sum(
                1 for row in rows
                if row["pair_status"] == "paired"
            ),
            "training_ready_count": len(ready),
            "missing_xmp_count": len(missing_xmp),
            "missing_targets_count": len(missing_targets),
            "invalid_or_error_count": len(invalid),
            "duplicate_raw_group_count": len(duplicates),
            "usable_event_count": len(usable_event_ids),
            "event_safe_split_ready": event_safe_split_ready,
        },
        "event_summaries": event_summaries,
        "duplicate_raw_groups": duplicates,
        "rows": rows,
        "readiness_gate": {
            "can_start_three_target_training": (
                len(ready) > 0
                and event_safe_split_ready
                and len(invalid) == 0
            ),
            "reasons": [
                reason
                for condition, reason in (
                    (
                        len(ready) == 0,
                        "no samples have all three Phase 12 targets",
                    ),
                    (
                        not event_safe_split_ready,
                        "fewer than two usable event groups; event-safe train/validation split is not possible",
                    ),
                    (
                        len(invalid) > 0,
                        "one or more paired XMP files have invalid or incomplete rendering context",
                    ),
                )
                if condition
            ],
        },
        "limits": [
            "This validator does not prove photographic representativeness.",
            "This validator does not decide whether the photographer edits are high quality.",
            "This validator does not parse Lightroom catalog-only edits without XMP sidecars.",
            "This validator does not train or evaluate any Brain.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument(
        "--preset-identity",
        default="none",
        help="Explicit known preset identity; use 'none' only when correct.",
    )
    parser.add_argument(
        "--tone-curve-identity",
        default=None,
        help="Optional known tone-curve identity override when XMP lacks one.",
    )
    parser.add_argument(
        "--skip-raw-hashes",
        action="store_true",
        help="Skip RAW SHA-256 hashing/duplicate detection for a faster first scan.",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Dataset root not found: {root}")

    report = build_report(
        root=root,
        preset_identity=args.preset_identity,
        tone_curve_identity=args.tone_curve_identity,
        hash_raws=not args.skip_raw_hashes,
    )

    output = (
        args.output.resolve()
        if args.output
        else Path.cwd().resolve().parent
        / "docs"
        / "runtime"
        / "phase12_dataset_readiness.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = report["summary"]
    gate = report["readiness_gate"]

    print("=== Phase 12 Dataset Readiness ===")
    print(f"events: {summary['event_count']}")
    print(f"RAWs: {summary['raw_count']}")
    print(f"paired XMP: {summary['paired_xmp_count']}")
    print(f"training-ready: {summary['training_ready_count']}")
    print(f"missing XMP: {summary['missing_xmp_count']}")
    print(f"missing targets: {summary['missing_targets_count']}")
    print(f"invalid/errors: {summary['invalid_or_error_count']}")
    print(f"duplicate RAW groups: {summary['duplicate_raw_group_count']}")
    print(f"usable events: {summary['usable_event_count']}")
    print(f"event-safe split ready: {summary['event_safe_split_ready']}")
    print(f"CAN START THREE-TARGET TRAINING: {gate['can_start_three_target_training']}")
    if gate["reasons"]:
        print("Blockers:")
        for reason in gate["reasons"]:
            print(f"- {reason}")
    print(f"Report: {output}")

    return 0 if gate["can_start_three_target_training"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
