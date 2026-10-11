"""RAW-CAT-01E.04A — read-only Lightroom Preview cache linkage probe.

Research only: database key overlap is NOT proof of the physical JPEG, RAW,
current/final edit, or photographic meaning. Output is aggregate and ID-free.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from app.photographer.raw_catalog_intake import _write_atomic

SCHEMA = "prographer.raw_catalog_preview_index.v1"
CATALOG_COLUMNS = {"Adobe_images": {"id_local", "id_global", "fileFormat"}}
PREVIEW_COLUMNS = {
    "ImageCacheEntry": {"imageId", "uuid", "digest"},
    "Pyramid": {"uuid", "digest"},
    "PyramidLevel": {"uuid", "digest", "level"},
}


class PreviewIndexError(ValueError):
    """Unverifiable inputs or schema; never silently assume joins."""


def _open_readonly(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise PreviewIndexError("input is not a regular SQLite file")
    wal = Path(str(path) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise PreviewIndexError("nonempty SQLite WAL: close Lightroom and use a finalized COPY")
    db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
    db.execute("PRAGMA query_only=ON")
    if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        db.close()
        raise PreviewIndexError("SQLite integrity check failed")
    return db


def _require_columns(db: sqlite3.Connection, required: dict[str, set[str]]) -> None:
    tables = {name for (name,) in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    for table, columns in required.items():
        if table not in tables:
            raise PreviewIndexError("unsupported schema: missing " + table)
        present = {column[1] for column in db.execute("PRAGMA table_info(" + table + ")")}
        if not columns <= present:
            raise PreviewIndexError(
                "unsupported schema: " + table + " missing " + ", ".join(sorted(columns - present))
            )


def _cache_database(directory: Path) -> Path:
    if not directory.is_dir() or not directory.name.lower().endswith("previews.lrdata"):
        raise PreviewIndexError("expected a Lightroom Previews.lrdata directory")
    databases = sorted(p for p in directory.rglob("*.db") if p.is_file())
    if len(databases) != 1:
        raise PreviewIndexError("expected exactly one preview index .db file")
    return databases[0]


def _jpeg_inventory(directory: Path, database: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for file in directory.rglob("*"):
        if not file.is_file() or file == database:
            continue
        if file.is_symlink():
            counts["symlink_files_skipped"] += 1
            continue
        with file.open("rb") as stream:
            signature = stream.read(3)
        if signature == b"\xff\xd8\xff":
            counts["jpeg_signature_files"] += 1
        else:
            counts["other_signature_files"] += 1
    return dict(sorted(counts.items()))


def inspect_preview_index(catalog: str | Path, preview_dir: str | Path) -> dict:
    """Check exact SQLite key overlaps and JPEG signatures, without exporting rows."""
    catalog = Path(catalog).expanduser().resolve(strict=True)
    preview_dir = Path(preview_dir).expanduser().resolve(strict=True)
    if not catalog.is_file() or catalog.suffix.lower() != ".lrcat":
        raise PreviewIndexError("catalog input must be an exported .lrcat COPY")
    database = _cache_database(preview_dir)
    jpeg_counts = _jpeg_inventory(preview_dir, database)

    with _open_readonly(catalog) as cat, _open_readonly(database) as previews:
        _require_columns(cat, CATALOG_COLUMNS)
        _require_columns(previews, PREVIEW_COLUMNS)
        photo_rows = list(cat.execute(
            "SELECT id_local, id_global, fileFormat FROM Adobe_images"
        ))
        cache_rows = list(previews.execute(
            "SELECT imageId, uuid, digest FROM ImageCacheEntry"
        ))
        pyramid_counts = Counter(previews.execute("SELECT uuid, digest FROM Pyramid"))
        level_keys = set(previews.execute("SELECT uuid, digest FROM PyramidLevel"))
        level_count = previews.execute("SELECT COUNT(*) FROM PyramidLevel").fetchone()[0]

    raw_rows = [p for p in photo_rows if str(p[2] or "").upper() == "RAW"]
    image_ids = [entry[0] for entry in cache_rows if entry[0] is not None]
    cache_ids = set(image_ids)
    raw_local = {p[0] for p in raw_rows if p[0] is not None}
    raw_global = {p[1] for p in raw_rows if p[1] is not None}
    all_local = {p[0] for p in photo_rows if p[0] is not None}
    all_global = {p[1] for p in photo_rows if p[1] is not None}
    raw_local_matches = len(raw_local & cache_ids)
    raw_global_matches = len(raw_global & cache_ids)

    cache_keys = [(entry[1], entry[2]) for entry in cache_rows]
    pyramid_match_counts = Counter(pyramid_counts.get(key, 0) for key in cache_keys)
    linked_cache_keys = [
        key for key in cache_keys if pyramid_counts.get(key, 0) == 1
    ]
    status = "KEY_OVERLAP_ONLY_NOT_PROVEN" if raw_local_matches or raw_global_matches else "NO_RAW_KEY_OVERLAP"

    return {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "RESEARCH_PREVIEW_INDEX_ONLY",
        "privacy": "AGGREGATE ONLY; no paths, filenames, photo IDs, cache keys or image pixels",
        "read_mode": "SQLite immutable/query_only; JPEG header read only",
        "catalog_counts": {
            "all_photo_rows": len(photo_rows),
            "raw_photo_rows": len(raw_rows),
        },
        "preview_file_signatures": jpeg_counts,
        "image_cache": {
            "entry_rows": len(cache_rows),
            "distinct_nonnull_image_ids": len(cache_ids),
            "null_image_id_rows": len(cache_rows) - len(image_ids),
            "duplicate_image_id_extra_rows": len(image_ids) - len(cache_ids),
        },
        "candidate_id_overlaps": {
            "catalog_id_local_all": len(all_local & cache_ids),
            "catalog_id_global_all": len(all_global & cache_ids),
            "catalog_id_local_raw": raw_local_matches,
            "catalog_id_global_raw": raw_global_matches,
            "raw_catalog_ids_without_local_cache_match": len(raw_local - cache_ids),
            "interpretation": status,
        },
        "pyramid_linkage": {
            "pyramid_rows": sum(pyramid_counts.values()),
            "distinct_pyramid_keys": len(pyramid_counts),
            "cache_rows_no_pyramid": pyramid_match_counts.get(0, 0),
            "cache_rows_exactly_one_pyramid": pyramid_match_counts.get(1, 0),
            "cache_rows_multiple_pyramids": sum(
                count for multiplicity, count in pyramid_match_counts.items()
                if multiplicity > 1
            ),
            "level_rows": level_count,
            "distinct_level_keys": len(level_keys),
            "cache_rows_one_pyramid_with_level": sum(key in level_keys for key in linked_cache_keys),
        },
        "physical_jpeg_to_photo_link_verified": False,
        "lightroom_or_xmp_parity_verified": False,
        "source_raw_verified": False,
        "training_ready_samples": 0,
        "warnings": [
            "Cache/imageId overlap is not proof of the same photograph or edit.",
            "Pyramid records and files are not yet paired by an audited, version-specific path rule.",
            "JPEG previews can be edited display derivatives, not pre-edit RAW data.",
            "No Lightroom XMP parity, approved original RAW, event split or finality was established.",
        ],
    }


def main() -> int:
    cli = argparse.ArgumentParser(
        description="ProGrapher Preview index research: aggregate, read-only, no training"
    )
    cli.add_argument("--catalog", type=Path, required=True)
    cli.add_argument("--previews-dir", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    args = cli.parse_args()
    report_path = args.report.expanduser().resolve()
    cat_path = args.catalog.expanduser().resolve()
    previews_path = args.previews_dir.expanduser().resolve()
    if report_path == cat_path or report_path == previews_path or previews_path in report_path.parents:
        cli.error("report must be separate from the catalog and Preview cache directory")
    try:
        report = inspect_preview_index(cat_path, previews_path)
        _write_atomic(report_path, report)
    except (OSError, sqlite3.Error, ValueError) as exc:
        cli.exit(2, "Preview index probe FAILED; input not modified: " + str(exc) + "\n")
    print("Aggregate report:", report_path)
    print("RAW catalog entries:", report["catalog_counts"]["raw_photo_rows"])
    print("Cache entries:", report["image_cache"]["entry_rows"])
    print("Local-ID RAW overlap candidates:", report["candidate_id_overlaps"]["catalog_id_local_raw"])
    print("Global-ID RAW overlap candidates:", report["candidate_id_overlaps"]["catalog_id_global_raw"])
    print("Physical JPEG/photo match: NOT VERIFIED; training-ready: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
