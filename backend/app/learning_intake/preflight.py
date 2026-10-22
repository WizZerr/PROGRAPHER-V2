"""PG-LI-02A: bounded, local-only RAW/catalog sample preflight.

This stage does NOT prove RAW↔Lightroom identity, final edit, event, starting
Develop state or training eligibility. All per-photo records remain private.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import os
from pathlib import Path
from typing import Any

from app.learning_intake.service import LearningIntakeError

MAX_SAMPLE = 16
MAX_SOURCE_FILES = 100_000
MAX_HASH_BYTES = 400 * 1024 * 1024


def _evenly_spaced(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministically shuffle a group to sample throughout the event."""
    if len(rows) < 2:
        return rows
    # Interleave both ends of the catalog-ID order to avoid inspecting
    # only the first imported records. IDs are NOT verified capture chronology.
    result: list[dict[str, Any]] = []
    front, back = 0, len(rows) - 1
    while front <= back:
        result.append(rows[front])
        if front != back:
            result.append(rows[back])
        front += 1
        back -= 1
    return result


def choose_sample(records: list[dict[str, Any]], sample_size: int = 16) -> list[dict[str, Any]]:
    if not 1 <= sample_size <= MAX_SAMPLE:
        raise LearningIntakeError("Sample size must be between 1 and 16.")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        group_id = str(row.get("event_group_id") or "unclassified")
        groups[group_id].append(row)
    by_group = {
        name: _evenly_spaced(sorted(items, key=lambda x: int(x.get("catalog_image_id") or 0)))
        for name, items in sorted(groups.items())
    }
    selection: list[dict[str, Any]] = []
    offsets = {name: 0 for name in by_group}
    while len(selection) < sample_size:
        added = False
        for name, items in by_group.items():
            index = offsets[name]
            if index >= len(items):
                continue
            selection.append(items[index])
            offsets[name] = index + 1
            added = True
            if len(selection) == sample_size:
                break
        if not added:
            break
    return selection


def _source_candidates(source_root: Path, wanted: set[str]) -> dict[str, list[Path]]:
    """Search bounded local directory, no symlink traversal or filename guesses."""
    found: dict[str, list[Path]] = defaultdict(list)
    visited = 0
    for directory, subdirs, filenames in os.walk(source_root, followlinks=False):
        base = Path(directory)
        subdirs[:] = sorted(d for d in subdirs if not (base / d).is_symlink())
        for filename in sorted(filenames):
            entry = base / filename
            if entry.is_symlink():
                continue
            visited += 1
            if visited > MAX_SOURCE_FILES:
                raise LearningIntakeError(
                    "RAW folder contains too many files for the 16-image preflight. Select a smaller event folder."
                )
            key = filename.casefold()
            if key in wanted and len(found[key]) < 2:
                found[key].append(entry)
    return found


def _fingerprint(path: Path) -> tuple[str | None, str]:
    try:
        before = path.stat()
        if before.st_size > MAX_HASH_BYTES:
            return None, "file_too_large_to_hash"
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            return None, "source_changed_during_read"
        return digest.hexdigest(), "fingerprint_recorded_identity_unverified"
    except OSError:
        return None, "source_unreadable"


def sample_preflight(private: dict[str, Any], *, raw_root: Path | None = None,
                     sample_size: int = 16) -> dict[str, Any]:
    """Return a local review sample, never a training manifest."""
    rows = choose_sample(private.get("records", []), sample_size)
    keys = {
        (str(item.get("file_stem") or "") + "." + str(item.get("extension") or "")).casefold()
        for item in rows
    }
    found = _source_candidates(raw_root, keys) if raw_root is not None else {}
    samples: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()

    for item in rows:
        stem = str(item.get("file_stem") or "")
        extension = str(item.get("extension") or "")
        filename = stem + "." + extension
        candidates = found.get(filename.casefold(), [])
        if raw_root is None:
            status = "raw_folder_not_selected"
        elif not stem or not extension:
            status = "missing_catalog_filename"
        elif len(candidates) > 1:
            status = "ambiguous_filename"
        elif not candidates:
            status = "no_filename_candidate"
        else:
            status = "unique_filename_candidate"
        digest: str | None = None
        path: str | None = None
        if status == "unique_filename_candidate":
            path = str(candidates[0])
            digest, fp_status = _fingerprint(candidates[0])
            if digest is None:
                status = fp_status
        statuses[status] += 1
        issues: list[str] = []
        if item.get("parse_exclusion"):
            issues.append(str(item["parse_exclusion"]))
        if item.get("virtual_copy_candidate"):
            issues.append("virtual_copy_requires_selection")
        if item.get("opaque_edit_review_required"):
            issues.append("unsupported_local_edit_review_required")
        if item.get("unsupported_fields"):
            issues.append("unmapped_develop_fields")

        samples.append({
            "catalog_image_id": item.get("catalog_image_id"),
            "catalog_global_image_id": item.get("catalog_global_image_id"),
            "filename": filename,
            "capture_day": item.get("capture_day"),
            "candidate_group": item.get("event_group_id"),
            "develop_parse_ok": not bool(item.get("parse_exclusion")),
            "develop_fields": sorted(item.get("develop", {}).keys()),
            "virtual_copy_candidate": bool(item.get("virtual_copy_candidate")),
            "issues": issues,
            "source_match_status": status,
            "source_candidate_path": path,
            "source_sha256": digest,
            "source_identity_verified": False,
            "photographer_finality_verified": False,
            "import_reset_baseline_verified": False,
            "event_identity_verified": False,
            "training_eligible": False,
        })

    return {
        "schema": "prographer.learning_intake.sample_preflight.v1",
        "status": "RESEARCH_ONLY_NOT_TRAINING_READY",
        "sample_count": len(samples),
        "sample_limit": MAX_SAMPLE,
        "group_count_in_sample": len(set(s["candidate_group"] for s in samples)),
        "source_match_counts": dict(sorted(statuses.items())),
        "source_identity_verified_count": 0,
        "finality_verified_count": 0,
        "training_ready_samples": 0,
        "records": samples,
        "warnings": [
            "Sample details are PRIVATE and provided only through the local authenticated engine; do not upload to GitHub.",
            "Filename+extension uniqueness and a SHA-256 of an observed RAW file are NOT an identity link to the Lightroom catalog.",
            "Candidate event groups are unapproved; duplicate/virtual-copy/finality/Import-vs-Reset checks are still blocked.",
            "Smart Previews folder-name detection is NOT pixel or catalog identity verification.",
        ],
    }
