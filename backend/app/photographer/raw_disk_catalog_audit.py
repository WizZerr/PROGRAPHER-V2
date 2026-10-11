"""RAW-CAT-01F.01A: read-only RAW disk to Lightroom catalog name audit.

Filename joins are only candidates, not content identity, final edits,
photographer consent or training eligibility. Shareable output is aggregate only.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.photographer.raw_catalog_intake import (
    RAW_EXTS, CatalogIntakeError, _write_atomic, inspect_catalog,
)

SCHEMA = "prographer.raw_disk_catalog_name_audit.v1"


def _key(stem: str, extension: str) -> tuple[str, str]:
    return stem.casefold(), extension.lstrip(".").casefold()


def audit(raw_dir: str | Path, catalog: str | Path) -> dict:
    root = Path(raw_dir).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("RAW source must be a directory")
    raw_names: Counter[tuple[str, str]] = Counter()
    file_counts: Counter[str] = Counter()
    ext_counts: Counter[str] = Counter()
    for item in root.rglob("*"):
        if item.is_symlink():
            file_counts["symlinks_skipped"] += 1
        elif item.is_file():
            if item.name.startswith("._"):
                file_counts["mac_metadata_skipped"] += 1
            elif item.suffix.lower().lstrip(".") not in RAW_EXTS:
                file_counts["other_files_skipped"] += 1
            else:
                ext = item.suffix.lower().lstrip(".")
                raw_names[_key(item.stem, ext)] += 1
                file_counts["raw_files"] += 1
                file_counts["raw_bytes"] += item.stat().st_size
                ext_counts[ext] += 1

    catalog_report, private = inspect_catalog(catalog, include_private=True)
    if private is None:
        raise ValueError("Lightroom parser returned no private rows")
    records = private["records"]
    cat_names: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in records:
        stem, extension = row.get("file_stem"), row.get("extension")
        if isinstance(stem, str) and stem.strip() and isinstance(extension, str):
            cat_names[_key(stem, extension)].append(row)

    counts: Counter[str] = Counter()
    groups: Counter[str] = Counter()
    for key in set(raw_names) | set(cat_names):
        disk_n, cat_rows = raw_names.get(key, 0), cat_names.get(key, [])
        if disk_n and cat_rows:
            if disk_n != 1 or len(cat_rows) != 1:
                counts["ambiguous_keys"] += 1
                counts["ambiguous_disk_files"] += disk_n
                counts["ambiguous_catalog_rows"] += len(cat_rows)
            else:
                counts["name_only_candidate_pairs"] += 1
                row = cat_rows[0]
                if row.get("parse_exclusion"):
                    counts["candidate_parse_excluded"] += 1
                elif row.get("virtual_copy_candidate"):
                    counts["candidate_virtual_copy_review"] += 1
                else:
                    counts["candidate_parsed_nonvirtual"] += 1
                groups[str(row.get("event_group_id") or "UNKNOWN")] += 1
        elif disk_n:
            counts["unmatched_disk_raw"] += disk_n
        else:
            counts["unmatched_catalog_rows"] += len(cat_rows)
    counts["catalog_rows_missing_filename"] = len(records) - sum(map(len, cat_names.values()))
    for key in ("name_only_candidate_pairs", "ambiguous_keys", "ambiguous_disk_files",
                "ambiguous_catalog_rows", "unmatched_disk_raw", "unmatched_catalog_rows",
                "catalog_rows_missing_filename", "candidate_parse_excluded",
                "candidate_virtual_copy_review", "candidate_parsed_nonvirtual"):
        counts.setdefault(key, 0)

    return {
        "schema": SCHEMA,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PRE_G0_NAME_MATCH_ONLY",
        "privacy": "AGGREGATE ONLY; no filenames, source paths, dates, IDs, Develop targets or photo pixels",
        "disk": {
            "raw_files": file_counts["raw_files"],
            "raw_bytes": file_counts["raw_bytes"],
            "raw_extensions": dict(sorted(ext_counts.items())),
            "mac_metadata_skipped": file_counts["mac_metadata_skipped"],
            "other_files_skipped": file_counts["other_files_skipped"],
            "symlinks_skipped": file_counts["symlinks_skipped"],
        },
        "catalog_raw_rows": len(records),
        "catalog_parse_exclusions": catalog_report.get("exclusions", {}),
        "name_join": dict(sorted(counts.items())),
        "tentative_group_counts": dict(sorted(groups.items())),
        "raw_identity_sha_verified": 0,
        "photographer_approved_pairs": 0,
        "confirmed_events": 0,
        "training_eligible_pairs": 0,
        "warning": "No RAW pixels, SHA256 content identity, finality, consent, scene or event verification",
    }


def main() -> int:
    cli = argparse.ArgumentParser(description="Read-only private RAW source ↔ Lightroom catalog aggregate audit")
    cli.add_argument("--raw-dir", type=Path, required=True)
    cli.add_argument("--catalog", type=Path, required=True, help="CLOSED exported Lightroom .lrcat COPY")
    cli.add_argument("--report", type=Path, required=True)
    args = cli.parse_args()
    try:
        root = args.raw_dir.expanduser().resolve(strict=True)
        catalog = args.catalog.expanduser().resolve(strict=True)
        output = args.report.expanduser().resolve()
        if output == catalog or output.is_relative_to(root):
            raise ValueError("Output must NOT be inside the RAW source folder or overwrite the catalog")
        report = audit(root, catalog)
        _write_atomic(output, report)
    except (CatalogIntakeError, OSError, ValueError) as exc:
        cli.exit(2, f"RAW SOURCE AUDIT FAILED (no source changes): {exc}\n")
    print("Aggregate report:", output)
    print("Disk RAW:", report["disk"]["raw_files"])
    print("Catalog RAW:", report["catalog_raw_rows"])
    print("Filename-only candidates:", report["name_join"]["name_only_candidate_pairs"])
    print("Ambiguous keys:", report["name_join"]["ambiguous_keys"])
    print("Unmatched disk RAW:", report["name_join"]["unmatched_disk_raw"])
    print("Unmatched catalog RAW:", report["name_join"]["unmatched_catalog_rows"])
    print("Verified training pairs: 0 (not evaluated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
