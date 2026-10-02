from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.testing.jpeg_pairs import scan_jpeg_pairs


SCHEMA_VERSION = 1
SPLIT_POLICY_VERSION = "event-hash-v1"
JPEG_EXTENSIONS = {".jpg", ".jpeg"}


@dataclass(frozen=True)
class PairRecord:
    pair_id: str
    event_id: str
    split: str
    status: str
    usable_for_recipe_fit: bool
    original_path: str
    edited_path: str
    original_relative_path: str
    edited_relative_path: str
    original_scan_fingerprint: str
    edited_scan_fingerprint: str
    original_sha256: str
    edited_sha256: str
    identical_bytes: bool
    same_physical_file: bool
    original_width: int | None
    original_height: int | None
    edited_width: int | None
    edited_height: int | None
    aspect_ratio_relative_error: float | None
    geometry_action: str
    note: str


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    event_path: str
    originals_path: str
    edits_path: str
    split: str
    original_files: int
    edited_files: int
    matched_pairs: int
    usable_pairs: int
    unchanged_pairs: int
    geometry_excluded_pairs: int
    decode_excluded_pairs: int
    physical_same_pairs: int
    unmatched_originals: int
    ambiguous_files: int
    ignored_non_jpeg: int
    j0_manifest_path: str | None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: Iterable[dict]) -> None:
    materialized = list(rows)
    if not materialized:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    seen: set[str] = set()
    for row in materialized:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(materialized)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode_dimensions(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    encoded = np.frombuffer(payload, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("jpeg_decode_failed")
    height, width = image.shape[:2]
    return int(width), int(height)


def _same_physical_file(left: Path, right: Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError:
        return left.resolve() == right.resolve()


def _safe_id(value: str) -> str:
    normalized = []
    for char in value.strip():
        if char.isalnum() or char in {"-", "_", "."}:
            normalized.append(char)
        else:
            normalized.append("_")
    result = "".join(normalized).strip("._")
    return result or "event"


def _find_required_child(event_path: Path, name: str) -> Path:
    matches = [
        child
        for child in event_path.iterdir()
        if child.is_dir() and child.name.casefold() == name.casefold()
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {name} folder in {event_path}; found {len(matches)}"
        )
    return matches[0].resolve(strict=True)


def _discover_events(root: Path) -> list[tuple[str, Path, Path, Path]]:
    events: list[tuple[str, Path, Path, Path]] = []
    seen_ids: set[str] = set()

    for event_path in sorted(
        (path for path in root.iterdir() if path.is_dir()),
        key=lambda path: path.name.casefold(),
    ):
        try:
            originals = _find_required_child(event_path, "ORIGINALS")
            edits = _find_required_child(event_path, "EDITS")
        except ValueError:
            continue

        event_id = _safe_id(event_path.name)
        if event_id.casefold() in seen_ids:
            raise ValueError(
                f"event ids collide after normalization: {event_path.name}"
            )
        seen_ids.add(event_id.casefold())
        events.append((event_id, event_path.resolve(), originals, edits))

    return events


def _auto_split(
    eligible_event_ids: list[str],
    photographer_id: str,
) -> dict[str, str]:
    count = len(eligible_event_ids)
    if count < 3:
        return {}

    validation_count = max(1, round(count * 0.20))
    test_count = max(1, round(count * 0.20))
    while validation_count + test_count >= count:
        if test_count > 1:
            test_count -= 1
        elif validation_count > 1:
            validation_count -= 1
        else:
            break

    ranked = sorted(
        eligible_event_ids,
        key=lambda event_id: hashlib.sha256(
            f"{SPLIT_POLICY_VERSION}|{photographer_id}|{event_id}".encode("utf-8")
        ).hexdigest(),
    )

    test_ids = set(ranked[:test_count])
    validation_ids = set(ranked[test_count : test_count + validation_count])

    return {
        event_id: (
            "test"
            if event_id in test_ids
            else "validation"
            if event_id in validation_ids
            else "train"
        )
        for event_id in eligible_event_ids
    }


def _explicit_split(
    eligible_event_ids: list[str],
    validation_events: list[str],
    test_events: list[str],
) -> dict[str, str]:
    known = set(eligible_event_ids)
    validation = {_safe_id(value) for value in validation_events}
    test = {_safe_id(value) for value in test_events}

    if not validation or not test:
        raise ValueError(
            "explicit split requires at least one --validation-event and one --test-event"
        )
    if validation & test:
        raise ValueError("an event cannot be both validation and test")
    unknown = (validation | test) - known
    if unknown:
        raise ValueError(
            "explicit split references unknown/ineligible events: "
            + ", ".join(sorted(unknown))
        )

    train = known - validation - test
    if not train:
        raise ValueError("explicit split leaves no train events")

    return {
        event_id: (
            "validation"
            if event_id in validation
            else "test"
            if event_id in test
            else "train"
        )
        for event_id in eligible_event_ids
    }


def _load_or_create_split_lock(
    *,
    path: Path,
    photographer_id: str,
    eligible_event_ids: list[str],
    validation_events: list[str],
    test_events: list[str],
    rebuild: bool,
) -> tuple[dict, list[str]]:
    explicit_requested = bool(validation_events or test_events)

    if path.exists() and not rebuild:
        if explicit_requested:
            raise ValueError(
                "split lock already exists; use --rebuild-split-lock to intentionally "
                "replace it with an explicit plan"
            )
        lock = _read_json(path)
        if lock.get("photographer_id") != photographer_id:
            raise ValueError(
                "existing split lock belongs to a different photographer_id"
            )

        assignments = dict(lock.get("assignments") or {})
        if not assignments and len(eligible_event_ids) >= 3:
            assignments = _auto_split(eligible_event_ids, photographer_id)
            lock = {
                "schema_version": SCHEMA_VERSION,
                "split_policy_version": SPLIT_POLICY_VERSION,
                "photographer_id": photographer_id,
                "created_at": _utc_now(),
                "mode": "auto",
                "assignments": assignments,
                "note": (
                    "Whole-event split lock. Existing assignments must not change "
                    "silently across training/evaluation runs."
                ),
            }
            _write_json(path, lock)
            return lock, []

        new_events = sorted(set(eligible_event_ids) - set(assignments))
        return lock, new_events

    if explicit_requested:
        assignments = _explicit_split(
            eligible_event_ids,
            validation_events,
            test_events,
        )
        mode = "explicit"
    else:
        assignments = _auto_split(eligible_event_ids, photographer_id)
        mode = "auto" if assignments else "insufficient_events"

    lock = {
        "schema_version": SCHEMA_VERSION,
        "split_policy_version": SPLIT_POLICY_VERSION,
        "photographer_id": photographer_id,
        "created_at": _utc_now(),
        "mode": mode,
        "assignments": assignments,
        "note": (
            "Whole-event split lock. Existing assignments must not change silently "
            "across training/evaluation runs. New events remain unassigned until an "
            "intentional split-lock rebuild."
        ),
    }
    _write_json(path, lock)
    return lock, []


def _geometry_status(
    original: Path,
    edited: Path,
    *,
    aspect_tolerance: float,
) -> tuple[
    str,
    bool,
    int | None,
    int | None,
    int | None,
    int | None,
    float | None,
    str,
]:
    try:
        ow, oh = _decode_dimensions(original)
        ew, eh = _decode_dimensions(edited)
    except (OSError, ValueError) as exc:
        return (
            "decode_error",
            False,
            None,
            None,
            None,
            None,
            None,
            str(exc),
        )

    original_ratio = ow / float(oh)
    edited_ratio = ew / float(eh)
    relative_error = abs(original_ratio - edited_ratio) / max(
        abs(edited_ratio),
        1e-9,
    )

    reciprocal_error = abs(original_ratio - (1.0 / edited_ratio)) / max(
        abs(1.0 / edited_ratio),
        1e-9,
    )
    if relative_error > aspect_tolerance:
        if reciprocal_error <= aspect_tolerance:
            return (
                "rotation_mismatch",
                False,
                ow,
                oh,
                ew,
                eh,
                relative_error,
                "90-degree orientation mismatch; exclude from first-pass recipe fitting",
            )
        return (
            "crop_or_geometry_mismatch",
            False,
            ow,
            oh,
            ew,
            eh,
            relative_error,
            "aspect ratio changed beyond tolerance; likely crop/geometry edit",
        )

    if (ow, oh) == (ew, eh):
        return (
            "same_dimensions",
            True,
            ow,
            oh,
            ew,
            eh,
            relative_error,
            "",
        )

    return (
        "resize_only",
        True,
        ow,
        oh,
        ew,
        eh,
        relative_error,
        "dimensions differ but aspect ratio is compatible; J0 may resize original",
    )


def _pair_id(event_id: str, relative_path: str, original_sha: str, edited_sha: str) -> str:
    payload = "|".join(
        (
            event_id,
            relative_path.casefold(),
            original_sha,
            edited_sha,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _event_j0_manifest(
    *,
    path: Path,
    photographer_id: str,
    event: EventRecord,
    pairs: list[PairRecord],
) -> None:
    usable = [pair for pair in pairs if pair.usable_for_recipe_fit]
    if not usable:
        return

    _write_json(
        path,
        {
            "schema_version": 1,
            "kind": "jpeg_pairs",
            "profile_id": f"real-{photographer_id}-{event.event_id}",
            "created_at": _utc_now(),
            "photographer_id": photographer_id,
            "event_label": event.event_id,
            "dataset_split": event.split,
            "originals_root": event.originals_path,
            "edits_root": event.edits_path,
            "pairs": [
                {
                    "pair_id": pair.pair_id,
                    "event_id": pair.event_id,
                    "split": pair.split,
                    "original_path": pair.original_path,
                    "edited_path": pair.edited_path,
                    "original_relative_path": pair.original_relative_path,
                    "edited_relative_path": pair.edited_relative_path,
                    # J0 uses these for identity rejection and deterministic seeds.
                    # Full SHA-256 is intentional for the research dataset.
                    "original_fingerprint": pair.original_sha256,
                    "edited_fingerprint": pair.edited_sha256,
                }
                for pair in usable
            ],
        },
    )


def _cross_split_duplicates(pairs: list[PairRecord]) -> list[dict]:
    by_original_sha: dict[str, list[PairRecord]] = {}
    for pair in pairs:
        if not pair.usable_for_recipe_fit:
            continue
        by_original_sha.setdefault(pair.original_sha256, []).append(pair)

    leaks: list[dict] = []
    for sha256, group in by_original_sha.items():
        splits = {pair.split for pair in group if pair.split in {"train", "validation", "test"}}
        if len(splits) <= 1:
            continue
        leaks.append(
            {
                "original_sha256": sha256,
                "splits": sorted(splits),
                "occurrences": [
                    {
                        "event_id": pair.event_id,
                        "split": pair.split,
                        "original_path": pair.original_path,
                    }
                    for pair in group
                ],
            }
        )
    return leaks


def _intake(
    *,
    root: Path,
    output: Path,
    photographer_id: str,
    aspect_tolerance: float,
    validation_events: list[str],
    test_events: list[str],
    rebuild_split_lock: bool,
) -> dict:
    discovered = _discover_events(root)
    if not discovered:
        raise ValueError(
            "No event folders were found. Expected ROOT/<event>/ORIGINALS and ROOT/<event>/EDITS."
        )

    # First pass: pair and validate without assigning train/validation/test yet.
    preliminary: dict[str, dict] = {}
    for event_id, event_path, originals, edits in discovered:
        scan = scan_jpeg_pairs(originals, edits)
        pair_rows: list[dict] = []

        for pair in scan.pairs:
            original = Path(pair.original_path)
            edited = Path(pair.edited_path)

            try:
                same_physical = _same_physical_file(original, edited)
                original_sha = _sha256(original)
                edited_sha = _sha256(edited)
            except OSError as exc:
                pair_rows.append(
                    {
                        "pair": pair,
                        "status": "read_error",
                        "usable": False,
                        "same_physical": False,
                        "original_sha": "",
                        "edited_sha": "",
                        "identical_bytes": False,
                        "geometry": (
                            "read_error",
                            False,
                            None,
                            None,
                            None,
                            None,
                            None,
                            str(exc),
                        ),
                    }
                )
                continue

            identical_bytes = original_sha == edited_sha
            geometry = _geometry_status(
                original,
                edited,
                aspect_tolerance=aspect_tolerance,
            )

            if same_physical:
                status = "same_physical_file"
                usable = False
            elif identical_bytes:
                # Preserve as a meaningful observation, but separate it from the
                # first recipe-target fitting pass. Phase 8 requires edited finals
                # and unedited/identity cases to be distinguishable.
                status = "unchanged_final"
                usable = False
            elif not geometry[1]:
                status = geometry[0]
                usable = False
            else:
                status = "usable"
                usable = True

            pair_rows.append(
                {
                    "pair": pair,
                    "status": status,
                    "usable": usable,
                    "same_physical": same_physical,
                    "original_sha": original_sha,
                    "edited_sha": edited_sha,
                    "identical_bytes": identical_bytes,
                    "geometry": geometry,
                }
            )

        preliminary[event_id] = {
            "event_path": event_path,
            "originals": originals,
            "edits": edits,
            "scan": scan,
            "pairs": pair_rows,
            "usable_pairs": sum(1 for row in pair_rows if row["usable"]),
        }

    eligible_event_ids = sorted(
        event_id
        for event_id, data in preliminary.items()
        if data["usable_pairs"] > 0
    )

    split_lock_path = output / "split_lock.json"
    split_lock, newly_unassigned = _load_or_create_split_lock(
        path=split_lock_path,
        photographer_id=photographer_id,
        eligible_event_ids=eligible_event_ids,
        validation_events=validation_events,
        test_events=test_events,
        rebuild=rebuild_split_lock,
    )
    assignments = dict(split_lock.get("assignments") or {})

    all_pairs: list[PairRecord] = []
    events: list[EventRecord] = []
    j0_dir = output / "j0_manifests"
    j0_dir.mkdir(parents=True, exist_ok=True)

    for event_id in sorted(preliminary):
        data = preliminary[event_id]
        split = assignments.get(event_id, "unassigned")
        pair_records: list[PairRecord] = []

        for row in data["pairs"]:
            pair = row["pair"]
            geometry = row["geometry"]
            note_parts = [part for part in (geometry[7],) if part]
            if row["status"] == "unchanged_final":
                note_parts.append(
                    "original and final JPEG bytes are identical; preserved separately "
                    "but excluded from first-pass J0 recipe target fitting"
                )
            if row["status"] == "same_physical_file":
                note_parts.append(
                    "original and edited resolve to the same physical file"
                )

            original_sha = row["original_sha"]
            edited_sha = row["edited_sha"]
            pair_record = PairRecord(
                pair_id=_pair_id(
                    event_id,
                    pair.original_relative_path,
                    original_sha or pair.original_fingerprint,
                    edited_sha or pair.edited_fingerprint,
                ),
                event_id=event_id,
                split=split,
                status=row["status"],
                usable_for_recipe_fit=bool(row["usable"]),
                original_path=pair.original_path,
                edited_path=pair.edited_path,
                original_relative_path=pair.original_relative_path,
                edited_relative_path=pair.edited_relative_path,
                original_scan_fingerprint=pair.original_fingerprint,
                edited_scan_fingerprint=pair.edited_fingerprint,
                original_sha256=original_sha,
                edited_sha256=edited_sha,
                identical_bytes=bool(row["identical_bytes"]),
                same_physical_file=bool(row["same_physical"]),
                original_width=geometry[2],
                original_height=geometry[3],
                edited_width=geometry[4],
                edited_height=geometry[5],
                aspect_ratio_relative_error=geometry[6],
                geometry_action=geometry[0],
                note="; ".join(note_parts),
            )
            pair_records.append(pair_record)
            all_pairs.append(pair_record)

        j0_manifest_path = (
            j0_dir / f"{split}__{event_id}.json"
            if any(pair.usable_for_recipe_fit for pair in pair_records)
            else None
        )

        scan = data["scan"]
        event_record = EventRecord(
            event_id=event_id,
            event_path=str(data["event_path"]),
            originals_path=str(data["originals"]),
            edits_path=str(data["edits"]),
            split=split,
            original_files=scan.original_files,
            edited_files=scan.edited_files,
            matched_pairs=scan.matched_pairs,
            usable_pairs=sum(pair.usable_for_recipe_fit for pair in pair_records),
            unchanged_pairs=sum(pair.status == "unchanged_final" for pair in pair_records),
            geometry_excluded_pairs=sum(
                pair.status in {"crop_or_geometry_mismatch", "rotation_mismatch"}
                for pair in pair_records
            ),
            decode_excluded_pairs=sum(
                pair.status in {"decode_error", "read_error"}
                for pair in pair_records
            ),
            physical_same_pairs=scan.identical_pairs
            + sum(pair.status == "same_physical_file" for pair in pair_records),
            unmatched_originals=scan.unmatched_files,
            ambiguous_files=scan.ambiguous_files,
            ignored_non_jpeg=scan.ignored_non_jpeg,
            j0_manifest_path=str(j0_manifest_path) if j0_manifest_path else None,
        )
        events.append(event_record)

        if j0_manifest_path is not None:
            _event_j0_manifest(
                path=j0_manifest_path,
                photographer_id=photographer_id,
                event=event_record,
                pairs=pair_records,
            )

    leaks = _cross_split_duplicates(all_pairs)

    split_counts = {
        split: sum(1 for event in events if event.split == split and event.usable_pairs > 0)
        for split in ("train", "validation", "test", "unassigned")
    }
    pair_split_counts = {
        split: sum(
            pair.usable_for_recipe_fit and pair.split == split
            for pair in all_pairs
        )
        for split in ("train", "validation", "test", "unassigned")
    }

    warnings: list[str] = []
    if len(eligible_event_ids) < 3:
        warnings.append(
            "Fewer than 3 usable events: a whole-event Train/Validation/Test evaluation "
            "cannot be formed yet."
        )
    if newly_unassigned:
        warnings.append(
            "New usable events were found after the split lock was created and remain "
            "unassigned: " + ", ".join(newly_unassigned)
        )
    if split_counts["unassigned"]:
        warnings.append(
            "At least one usable event is unassigned. Do not train/evaluate until the "
            "split lock is intentionally rebuilt."
        )
    if leaks:
        warnings.append(
            "The same original JPEG bytes occur across more than one locked split. "
            "This is cross-split leakage and blocks evaluation."
        )
    if any(event.ambiguous_files for event in events):
        warnings.append(
            "At least one event contains ambiguous JPEG names; those files were not paired."
        )
    if any(event.geometry_excluded_pairs for event in events):
        warnings.append(
            "Crop/orientation geometry mismatches were preserved in the report but excluded "
            "from first-pass recipe fitting."
        )
    if any(event.unchanged_pairs for event in events):
        warnings.append(
            "Byte-identical Original/Edited finals were preserved as unchanged-final cases "
            "and excluded from first-pass J0 recipe fitting."
        )

    evaluation_ready = bool(
        split_counts["train"] >= 1
        and split_counts["validation"] >= 1
        and split_counts["test"] >= 1
        and pair_split_counts["train"] >= 1
        and pair_split_counts["validation"] >= 1
        and pair_split_counts["test"] >= 1
        and split_counts["unassigned"] == 0
        and not leaks
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "jpeg_real_event_dataset",
        "created_at": _utc_now(),
        "photographer_id": photographer_id,
        "dataset_root": str(root),
        "output_root": str(output),
        "source_files_modified": False,
        "split_lock_path": str(split_lock_path),
        "split_policy_version": SPLIT_POLICY_VERSION,
        "aspect_tolerance": aspect_tolerance,
        "event_counts": split_counts,
        "usable_pair_counts": pair_split_counts,
        "totals": {
            "events_discovered": len(events),
            "events_with_usable_pairs": len(eligible_event_ids),
            "matched_pairs": sum(event.matched_pairs for event in events),
            "usable_recipe_pairs": sum(
                pair.usable_for_recipe_fit for pair in all_pairs
            ),
            "unchanged_final_pairs": sum(
                pair.status == "unchanged_final" for pair in all_pairs
            ),
            "geometry_excluded_pairs": sum(
                pair.status in {"crop_or_geometry_mismatch", "rotation_mismatch"}
                for pair in all_pairs
            ),
            "decode_or_read_excluded_pairs": sum(
                pair.status in {"decode_error", "read_error"} for pair in all_pairs
            ),
            "cross_split_duplicate_groups": len(leaks),
        },
        "readiness": {
            "pairing_data_present": any(event.matched_pairs > 0 for event in events),
            "j0_representation_test_ready": any(
                pair.usable_for_recipe_fit for pair in all_pairs
            ),
            "whole_event_train_validation_test_ready": evaluation_ready,
            "real_photographer_quality_claim_allowed": False,
        },
        "events": [asdict(event) for event in events],
        "pairs": [asdict(pair) for pair in all_pairs],
        "cross_split_duplicates": leaks,
        "warnings": warnings,
        "interpretation": (
            "This intake validates and freezes provenance for real Original JPEG + "
            "Photographer Edited JPEG material. It does not train a model and does not "
            "permit a photographer-quality claim. Whole events are the unit of split."
        ),
    }

    _write_json(output / "dataset_manifest.json", payload)
    _write_json(
        output / "evaluation_plan.json",
        {
            "schema_version": 1,
            "photographer_id": photographer_id,
            "split_lock_path": str(split_lock_path),
            "train_events": sorted(
                event.event_id for event in events if event.split == "train"
            ),
            "validation_events": sorted(
                event.event_id for event in events if event.split == "validation"
            ),
            "test_events": sorted(
                event.event_id for event in events if event.split == "test"
            ),
            "unassigned_events": sorted(
                event.event_id for event in events if event.split == "unassigned"
            ),
            "rules": [
                "Fit/train candidates only on Train events.",
                "Choose model/representation changes on Validation events.",
                "Keep Test events locked for final audit; do not tune against them.",
                "Do not move copies of the same source across splits.",
                "Run J0 per-pair reconstruction only as representation feasibility, not prediction.",
                "A real quality claim requires representative professional material and human review.",
            ],
        },
    )
    _write_csv(
        output / "event_report.csv",
        [asdict(event) for event in events],
    )
    _write_csv(
        output / "pair_report.csv",
        [asdict(pair) for pair in all_pairs],
    )

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and freeze a real JPEG photographer dataset organized as "
            "ROOT/<event>/ORIGINALS and ROOT/<event>/EDITS."
        )
    )
    parser.add_argument("--root", required=True, help="Root containing event folders")
    parser.add_argument("--output", required=True, help="Destination for manifests/reports")
    parser.add_argument(
        "--photographer-id",
        required=True,
        help="Stable non-secret photographer/profile identifier",
    )
    parser.add_argument(
        "--aspect-tolerance",
        type=float,
        default=0.01,
        help="Maximum relative aspect-ratio difference for first-pass alignment (default 0.01)",
    )
    parser.add_argument(
        "--validation-event",
        action="append",
        default=[],
        help="Explicit event id/name for Validation; repeatable",
    )
    parser.add_argument(
        "--test-event",
        action="append",
        default=[],
        help="Explicit event id/name for locked Test; repeatable",
    )
    parser.add_argument(
        "--rebuild-split-lock",
        action="store_true",
        help="Intentionally replace an existing split lock",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("--root must be a directory")
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    payload = _intake(
        root=root,
        output=output,
        photographer_id=args.photographer_id.strip(),
        aspect_tolerance=max(0.0, float(args.aspect_tolerance)),
        validation_events=list(args.validation_event),
        test_events=list(args.test_event),
        rebuild_split_lock=bool(args.rebuild_split_lock),
    )

    print("=" * 80)
    print("ProGrapher — Real JPEG Dataset Intake")
    print("=" * 80)
    print(f"Photographer:                    {payload['photographer_id']}")
    print(f"Events discovered:               {payload['totals']['events_discovered']}")
    print(f"Events with usable pairs:        {payload['totals']['events_with_usable_pairs']}")
    print(f"Matched pairs:                   {payload['totals']['matched_pairs']}")
    print(f"Usable J0 recipe pairs:          {payload['totals']['usable_recipe_pairs']}")
    print(f"Unchanged final pairs:           {payload['totals']['unchanged_final_pairs']}")
    print(f"Geometry exclusions:             {payload['totals']['geometry_excluded_pairs']}")
    print(f"Cross-split duplicate groups:    {payload['totals']['cross_split_duplicate_groups']}")
    print()
    print(
        "Event split counts:               "
        f"train={payload['event_counts']['train']} "
        f"validation={payload['event_counts']['validation']} "
        f"test={payload['event_counts']['test']} "
        f"unassigned={payload['event_counts']['unassigned']}"
    )
    print(
        "Whole-event evaluation ready:     "
        + (
            "YES"
            if payload["readiness"]["whole_event_train_validation_test_ready"]
            else "NO"
        )
    )
    print(f"Output:                           {payload['output_root']}")

    if payload["warnings"]:
        print()
        print("Warnings:")
        for warning in payload["warnings"]:
            print(f"- {warning}")

    print()
    print("Source JPEG files were read only; no source file was modified.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
