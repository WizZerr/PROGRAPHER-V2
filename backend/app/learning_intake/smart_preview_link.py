"""PG-LI-03 — link each Smart Preview DNG to its Lightroom catalog photo (the "before" half of a pair).

Lightroom names every Smart Preview after a catalog UUID (the photo's or its file's id_global) and records the
source RAW's name inside the DNG (OriginalRawFileName). A link counts as name-verified only when both agree.
Read only: catalogs are read through the existing consistent snapshot, DNGs through bounded metadata reads.
Virtual copies share their master's Smart Preview: one "before" image, several Develop records, never several
independent examples. Nothing here makes a sample training-ready; links are returned in memory, not stored.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from app.learning_intake.dng_diagnostics import read_original_raw_file_name

LINKED_VERIFIED = "linked_name_verified"
LINKED_MISMATCH = "linked_name_mismatch"
LINKED_UNREADABLE = "linked_name_unreadable"
NO_PREVIEW = "no_smart_preview"
AMBIGUOUS = "ambiguous_smart_preview"


def build_links(dng_files: list[Path], records: list[dict]) -> dict[str, Any]:
    """Match catalog RAW records to Smart Preview DNGs. Returns private per-record links plus aggregates."""
    by_stem: dict[str, list[Path]] = {}
    for path in dng_files:
        by_stem.setdefault(path.stem.casefold(), []).append(path)

    links: list[dict[str, Any]] = []
    users: Counter[str] = Counter()
    names: dict[str, str | None] = {}
    for rec in records:
        found: list[Path] = []
        matched_by = None
        for key, label in (("catalog_global_image_id", "image_uuid"), ("catalog_global_file_id", "file_uuid")):
            ident = rec.get(key)
            if isinstance(ident, str) and by_stem.get(ident.casefold()):
                found, matched_by = by_stem[ident.casefold()], label
                break
        link: dict[str, Any] = {"record": rec, "dng": None, "matched_by": matched_by,
                                "virtual_copy_candidate": bool(rec.get("virtual_copy_candidate"))}
        if not found:
            link["status"] = NO_PREVIEW
        elif len(found) > 1:
            link["status"] = AMBIGUOUS
        else:
            dng = found[0]
            key = str(dng).casefold()
            if key not in names:
                names[key] = read_original_raw_file_name(dng)
            original = names[key]
            expected = f"{rec.get('file_stem') or ''}.{rec.get('extension') or ''}".casefold()
            link["dng"] = dng
            users[key] += 1
            link["status"] = (LINKED_UNREADABLE if original is None
                              else LINKED_VERIFIED if original.casefold() == expected else LINKED_MISMATCH)
        links.append(link)

    for link in links:
        link["shares_preview"] = link["dng"] is not None and users[str(link["dng"]).casefold()] > 1
    used = {str(link["dng"]).casefold() for link in links if link["dng"] is not None}
    counts = Counter(link["status"] for link in links)
    return {
        "links": links,
        "catalog_raw_records": len(records),
        "smart_preview_files": len(dng_files),
        "status_counts": dict(sorted(counts.items())),
        "matched_by_counts": dict(sorted(Counter(l["matched_by"] for l in links if l["matched_by"]).items())),
        "virtual_copy_records": sum(link["virtual_copy_candidate"] for link in links),
        "records_sharing_a_preview": sum(link["shares_preview"] for link in links),
        "orphan_smart_previews": len(dng_files) - len(used),
    }


def link_report(preview_root: Path, records: list[dict], *, sample_size: int = 4) -> dict[str, Any]:
    """Aggregate link evidence plus up to `sample_size` linked photos with their rendered "before" image,
    so a person can compare them with Lightroom by name. Per-photo rows are transient and local-only."""
    from app.learning_intake.smart_preview_probe import _count_dng_files, _decode_sample

    counts, dngs = _count_dng_files(preview_root)
    result = build_links(dngs, records)
    verified = [l for l in result["links"] if l["status"] == LINKED_VERIFIED and not l["shares_preview"]]
    picks = [verified[i * len(verified) // sample_size] for i in range(min(sample_size, len(verified)))] \
        if sample_size else []
    samples = []
    for link in picks:
        rec = link["record"]
        decoded = _decode_sample(link["dng"])
        samples.append({
            "file_name": f"{rec.get('file_stem')}.{rec.get('extension')}",
            "capture_day": rec.get("capture_day"),
            "link_status": link["status"],
            "matched_by": link["matched_by"],
            "decode_state": decoded.get("state"),
            "reset_render": decoded.get("reset_render"),
        })
    return {
        "schema": "prographer.learning_intake.smart_preview_links.v1",
        "status": "CATALOG_LINK_RESEARCH_ONLY",
        "dng_inventory": counts,
        **{k: v for k, v in result.items() if k != "links"},
        "linked_name_verified": result["status_counts"].get(LINKED_VERIFIED, 0),
        "samples": samples,
        "photo_to_dng_link_verified": False,
        "photographer_finality_verified": False,
        "training_ready_samples": 0,
        "warnings": [
            "A link is name-verified when the catalog UUID names the DNG AND the DNG's OriginalRawFileName equals the catalog file name; it is not a byte-level RAW identity proof.",
            "Virtual copies share their master's Smart Preview: one 'before' image, several Develop records.",
            "File names in samples are shown locally for checking against Lightroom and are not stored.",
            "Develop targets and edit finality are not read here; no sample is training-ready.",
        ],
    }
