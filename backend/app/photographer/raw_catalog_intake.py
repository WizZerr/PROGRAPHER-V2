"""RAW-CAT-01D: isolated, read-only Lightroom Classic catalog inventory.

Engineering preparation only. No RAW bytes, export, training, or Lightroom
semantic parity claims. All per-photo records are PRIVATE. Standard library.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any

from app.photographer.curve_semantics import describe_curve
from app.photographer.develop_color_semantics import (
    COLOR_FIELDS, COLOR_FAMILIES, OPAQUE_FIELDS, OPAQUE_LOCAL_FIELDS,
    PROFILE_CONTEXT_FIELDS, parse_color_scalar, describe_opaque_field,
)

SCHEMA = "prographer.raw_catalog_intake.v1"
RAW_EXTS = frozenset("cr2 cr3 nef arw dng raf rw2 orf pef srw 3fr iiq raw nrw erf kdc mos mrw".split())
NUMERIC = frozenset("Exposure2012 Contrast2012 Highlights2012 Shadows2012 Whites2012 Blacks2012 Clarity2012 Texture Dehaze Vibrance Saturation Temperature Tint Sharpness LuminanceSmoothing".split())
TEXT = frozenset("ProcessVersion CameraProfile WhiteBalance ToneCurveName2012".split())
BOOL = frozenset(("ConvertToGrayscale",))
COMPLEX = frozenset(("ToneCurvePV2012", "ToneCurvePV2012Red", "ToneCurvePV2012Green", "ToneCurvePV2012Blue"))
WORD = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
ATOM = re.compile(r"[^,}\s]+")
BLOCK = re.compile(r"\bs\s*=\s*\{")
ISODAY = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[ T]|$)")
REQUIRED = {
    "Adobe_images": {"id_local", "id_global", "rootFile", "fileFormat", "captureTime", "originalCaptureTime", "masterImage", "copyName"},
    "AgLibraryFile": {"id_local", "id_global", "baseName", "extension", "folder"},
    "AgLibraryFolder": {"id_local", "rootFolder", "pathFromRoot"},
    "AgLibraryRootFolder": {"id_local", "name"},
    "Adobe_imageDevelopSettings": {"id_local", "image", "text", "processVersion", "whiteBalance", "grayscale"},
}


class CatalogIntakeError(ValueError):
    """Unsupported/corrupt catalog or unsafe input."""


def _ws(s: str, p: int) -> int:
    while p < len(s) and s[p].isspace():
        p += 1
    return p


def _quoted(s: str, p: int) -> tuple[str, int]:
    quote = s[p]
    p += 1
    chars: list[str] = []
    while p < len(s):
        c = s[p]
        if c == "\\":
            p += 1
            if p >= len(s):
                raise ValueError("unterminated string escape")
            chars.append({"n": "\n", "r": "\r", "t": "\t"}.get(s[p], s[p]))
        elif c == quote:
            return "".join(chars), p + 1
        else:
            chars.append(c)
        p += 1
    raise ValueError("unterminated string")


def _braced(s: str, p: int) -> tuple[str, int]:
    start, depth = p, 0
    while p < len(s):
        c = s[p]
        if c in "\"'":
            _, p = _quoted(s, p)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start:p + 1], p + 1
        p += 1
    raise ValueError("unterminated nested settings")


def parse_develop_settings(serialized: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    """Tokenize top-level Lightroom Lua-like settings without executing Lua.

    Unsupported scalar/nested fields are inventoried, not silently interpreted.
    Supported flat point-curves retain syntactic coordinates (not Adobe-validated).
    Unknown/complex structures remain fingerprints, never fabricated targets.
    """
    found = BLOCK.search(serialized)
    if found is None:
        raise ValueError("missing Lightroom s={ block")
    pos = found.end()
    values: dict[str, Any] = {}
    complex_fields: dict[str, dict[str, Any]] = {}
    present: list[str] = []
    while True:
        pos = _ws(serialized, pos)
        if pos >= len(serialized):
            raise ValueError("unterminated settings block")
        if serialized[pos] == "}":
            return values, complex_fields, present
        if serialized[pos] == ",":
            pos += 1
            continue
        match = WORD.match(serialized, pos)
        if match is None:
            raise ValueError(f"invalid key at offset {pos}")
        key = match.group(0)
        if key in present:
            raise ValueError(f"duplicate Develop field {key}")
        present.append(key)
        pos = _ws(serialized, match.end())
        if pos >= len(serialized) or serialized[pos] != "=":
            raise ValueError(f"missing equals for {key}")
        pos = _ws(serialized, pos + 1)
        if pos >= len(serialized):
            raise ValueError("missing value")
        nested = serialized[pos] == "{"
        if nested:
            val, pos = _braced(serialized, pos)
        elif serialized[pos] in "\"'":
            val, pos = _quoted(serialized, pos)
        else:
            token = ATOM.match(serialized, pos)
            if token is None:
                raise ValueError(f"invalid value for {key}")
            val = token.group(0)
            pos = token.end()
        if key in COMPLEX:
            complex_fields[key] = describe_curve(val)
        elif key in OPAQUE_FIELDS:
            complex_fields[key] = describe_opaque_field(val, nested=nested)
        elif key in COLOR_FIELDS:
            values[key] = parse_color_scalar(key, val, nested=nested)
        elif key in NUMERIC and not nested:
            try:
                number = float(val)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"invalid number for {key}") from exc
            if not math.isfinite(number):
                raise ValueError(f"nonfinite number for {key}")
            values[key] = number
        elif key in TEXT and not nested:
            values[key] = val
        elif key in BOOL and not nested:
            if val not in ("true", "false"):
                raise ValueError(f"invalid boolean for {key}")
            values[key] = (val == "true")


def _capture_day(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    match = ISODAY.match(value)
    if not match:
        return "unknown"
    try:
        date.fromisoformat(match.group(1))
    except ValueError:
        return "unknown"
    return match.group(1)


def _assert_schema(db: sqlite3.Connection) -> None:
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table, required_columns in REQUIRED.items():
        if table not in tables:
            raise CatalogIntakeError(f"unsupported catalog schema; missing table {table}")
        columns = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
        if not required_columns <= columns:
            raise CatalogIntakeError(f"unsupported catalog schema; {table} missing {sorted(required_columns-columns)}")


def inspect_catalog(catalog: str | Path, *, include_private: bool = False) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Return a path-free aggregate report and opt-in local/private manifest.

    Every row is catalog-only / NOT TRAINING-READY; group IDs are tentative.
    """
    path = Path(catalog).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() != ".lrcat":
        raise CatalogIntakeError("input must be a regular exported .lrcat copy")
    wal = Path(str(path) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise CatalogIntakeError("nonempty WAL; close Lightroom and use finalized exported copy. Do not delete sidecars")
    report_counts: Counter[str] = Counter()
    exclusions: Counter[str] = Counter()
    fields: Counter[str] = Counter()
    unsupported: Counter[str] = Counter()
    curve_stats: dict[str, Counter[str]] = {}
    color_family_stats: dict[str, Counter[str]] = {family: Counter() for family in COLOR_FAMILIES}
    color_field_stats: dict[str, Counter[str]] = {}
    profile_stats: dict[str, Counter[str]] = {}
    local_edit_stats: dict[str, Counter[str]] = {}
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    private_group_keys: list[tuple[Any, ...]] = []
    uri = path.as_uri() + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise CatalogIntakeError("catalog SQLite integrity check failed")
        _assert_schema(db)
        report_counts["catalog_photo_records"] = db.execute("SELECT COUNT(*) FROM Adobe_images").fetchone()[0]
        query = """
            SELECT i.id_local image_id, i.id_global global_image_id, i.fileFormat file_format,
                   i.masterImage master_image, i.copyName copy_name,
                   COALESCE(i.originalCaptureTime, i.captureTime) photo_time,
                   f.id_local file_id, f.id_global global_file_id, f.baseName base_name,
                   f.extension extension, f.folder folder_id,
                   folder.pathFromRoot folder_name, folder.rootFolder root_id,
                   root.name root_name,
                   d.id_local develop_id, d.text develop_text, d.grayscale grayscale
            FROM Adobe_images i
            LEFT JOIN AgLibraryFile f ON f.id_local = i.rootFile
            LEFT JOIN AgLibraryFolder folder ON folder.id_local = f.folder
            LEFT JOIN AgLibraryRootFolder root ON root.id_local = folder.rootFolder
            LEFT JOIN Adobe_imageDevelopSettings d ON d.image = i.id_local
            WHERE UPPER(i.fileFormat) = 'RAW'
            ORDER BY i.id_local, d.id_local
        """
        rows = db.execute(query)
        pending: list[sqlite3.Row] = []

        def consume(group: list[sqlite3.Row]) -> None:
            row = group[0]
            report_counts["catalog_raw_records"] += 1
            extension = str(row["extension"] or "").lower().lstrip(".")
            group_key = (row["root_id"], row["folder_id"], _capture_day(row["photo_time"]))
            if group_key not in grouped:
                grouped[group_key] = {"raw_count": 0, "parsed_count": 0, "bw_count": 0}
            grouped[group_key]["raw_count"] += 1
            reason: str | None = None
            develop: dict[str, Any] = {}
            complex_fields: dict[str, Any] = {}
            present: list[str] = []
            if len(group) != 1:
                reason = "ambiguous_develop_rows"
            elif row["file_id"] is None or row["folder_id"] is None:
                reason = "missing_source_catalog_link"
            elif extension not in RAW_EXTS:
                reason = "unsupported_raw_extension"
            elif row["develop_id"] is None or not row["develop_text"]:
                reason = "missing_develop"
            else:
                try:
                    raw_text = row["develop_text"]
                    if isinstance(raw_text, bytes):
                        raw_text = raw_text.decode("utf-8")
                    develop, complex_fields, present = parse_develop_settings(raw_text)
                except (ValueError, UnicodeError):
                    reason = "develop_parse_failed"
            if reason:
                exclusions[reason] += 1
            else:
                report_counts["parsed_raw_records"] += 1
                grouped[group_key]["parsed_count"] += 1
                for key in present:
                    fields[key] += 1
                    if key not in (NUMERIC | TEXT | BOOL | COMPLEX | COLOR_FIELDS):
                        unsupported[key] += 1
                for curve_key, meta in complex_fields.items():
                    if curve_key not in COMPLEX:
                        continue
                    if curve_key not in curve_stats:
                        curve_stats[curve_key] = Counter()
                    c = curve_stats[curve_key]
                    c["present"] += 1
                    c["decoded" if meta["decoded"] else "undecoded"] += 1
                    if meta["decoded"]:
                        c["linear" if meta["is_linear"] else "nonlinear"] += 1
                    else:
                        c["reason:" + str(meta.get("undecoded_reason", "unknown"))] += 1
                # Absence is not an explicit zero; counts are syntax only.
                for field in COLOR_FIELDS:
                    if field in develop:
                        c = color_field_stats.setdefault(field, Counter())
                        c["present"] += 1
                        c["explicit_zero" if develop[field] == 0 else "nonzero"] += 1
                for family, family_fields in COLOR_FAMILIES.items():
                    seen = [develop[k] for k in family_fields if k in develop]
                    c = color_family_stats[family]
                    if seen:
                        c["records_with_field"] += 1
                        c["observed_values"] += len(seen)
                        c["explicit_zero_values"] += sum(v == 0 for v in seen)
                        c["nonzero_values"] += sum(v != 0 for v in seen)
                        if any(v != 0 for v in seen):
                            c["records_with_nonzero_field"] += 1
                for field in PROFILE_CONTEXT_FIELDS:
                    if field in develop or field in complex_fields:
                        c = profile_stats.setdefault(field, Counter())
                        c["present"] += 1
                        if field in complex_fields:
                            c["opaque_not_decoded"] += 1
                            if complex_fields[field]["structure_nonempty"]:
                                c["structure_nonempty"] += 1
                        else:
                            c["scalar_parsed"] += 1
                for field in OPAQUE_LOCAL_FIELDS:
                    if field in complex_fields:
                        c = local_edit_stats.setdefault(field, Counter())
                        c["present"] += 1
                        c["opaque_not_decoded"] += 1
                        c["structure_nonempty" if complex_fields[field]["structure_nonempty"] else "structure_empty"] += 1
                if develop.get("ConvertToGrayscale") is True or row["grayscale"] == 1:
                    report_counts["grayscale_raw_records"] += 1
                    grouped[group_key]["bw_count"] += 1
            if include_private:
                private_group_keys.append(group_key)
                records.append({
                    "catalog_image_id": row["image_id"],
                    "catalog_global_image_id": row["global_image_id"],
                    "catalog_file_id": row["file_id"],
                    "catalog_global_file_id": row["global_file_id"],
                    "file_stem": row["base_name"], "extension": extension,
                    "catalog_root_name": row["root_name"], "catalog_folder": row["folder_name"],
                    "capture_day": group_key[2], "event_group_id": None,
                    "virtual_copy_candidate": row["master_image"] is not None or bool(row["copy_name"]),
                    "develop": develop, "complex": complex_fields,
                    "unsupported_fields": sorted(set(present)-(NUMERIC | TEXT | BOOL | COMPLEX | COLOR_FIELDS)),
                    "color_semantics_validated": False,
                    "opaque_edit_review_required": any(
                        complex_fields.get(field, {}).get("structure_nonempty", False)
                        for field in OPAQUE_LOCAL_FIELDS
                    ),
                    "parse_exclusion": reason, "status": "catalog_only_pending_source_and_finality" if not reason else "quarantined",
                    "source_raw_verified": False, "final_edit_confirmed": False,
                    "event_confirmed": False, "training_eligible": False,
                })

        for r in rows:
            if pending and r["image_id"] != pending[0]["image_id"]:
                consume(pending)
                pending = []
            pending.append(r)
        if pending:
            consume(pending)

    groups_sorted = sorted(grouped.items(), key=lambda pair: (-pair[1]["raw_count"], str(pair[0])))
    group_ids = {key: f"G{index:04d}" for index, (key, _) in enumerate(groups_sorted, 1)}
    if include_private:
        for rec, key in zip(records, private_group_keys):
            rec["event_group_id"] = group_ids[key]  # candidate only; requires human event confirmation
    shareable = {
        "schema": SCHEMA, "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "RAW_CATALOG_RESEARCH_ONLY", "read_mode": "SQLite immutable query_only",
        "privacy": "AGGREGATE ONLY; no source filenames, folder names, dates, image IDs or pixel data",
        "totals": dict(sorted(report_counts.items())),
        "exclusions": dict(sorted(exclusions.items())),
        "candidate_folder_day_groups": len(groups_sorted),
        "candidate_groups": [{"group_id": group_ids[key], "raw_count": val["raw_count"], "parsed_count": val["parsed_count"], "bw_count": val["bw_count"]} for key, val in groups_sorted],
        "develop_field_presence": dict(sorted(fields.items())),
        "unmapped_field_presence": dict(sorted(unsupported.items())),
        "curve_decode_coverage": {
            field: dict(sorted(counts.items()))
            for field, counts in sorted(curve_stats.items())
        },
        "curve_decoder": "flat_numeric_0_255_syntax_only; NOT Lightroom-validated",
        "color_decoder": "finite_scalars; explicit_zero_vs_absent; NOT Lightroom-validated",
        "color_family_coverage": {family: dict(sorted(counts.items())) for family, counts in sorted(color_family_stats.items())},
        "color_field_coverage": {field: dict(sorted(counts.items())) for field, counts in sorted(color_field_stats.items())},
        "profile_field_coverage": {field: dict(sorted(counts.items())) for field, counts in sorted(profile_stats.items())},
        "opaque_local_edit_coverage": {field: dict(sorted(counts.items())) for field, counts in sorted(local_edit_stats.items())},
        "training_ready_samples": 0,
        "warnings": ["No original RAW bytes verified", "No verified events / photographer-approved final edits", "Lightroom private schema: verify against Adobe Lightroom/XMP across versions", "Unknown keys and curves are NOT equivalent to decoded controls", "Curve point decoding is syntactic only; Adobe/LR/XMP parity is NOT verified", "Color fields are syntactic numeric extraction only; missing does not mean zero", "Opaque profile/mask/retouch fields are not interpreted as active edits", "History/preset/auto origin is NOT inferred"],
    }
    private = None
    if include_private:
        private = {"schema": SCHEMA, "privacy": "LOCAL ONLY: filenames, folders, photo IDs; DO NOT UPLOAD", "training_ready_samples": 0, "records": records}
    return shareable, private


def _write_atomic(path: Path, content: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".pg-raw-cat-", suffix=".tmp", delete=False) as f:
            temp = f.name
            json.dump(content, f, indent=2, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        os.replace(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def main() -> int:
    cli = argparse.ArgumentParser(description="ProGrapher RAW catalog engineering inventory (read-only)")
    cli.add_argument("--catalog", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    cli.add_argument("--local-manifest", type=Path)
    args = cli.parse_args()
    outputs = [args.report] + ([args.local_manifest] if args.local_manifest else [])
    if any(p.resolve() == args.catalog.resolve() for p in outputs) or len({p.resolve() for p in outputs}) != len(outputs):
        cli.error("output paths cannot overwrite each other or the Lightroom catalog")
    try:
        report, private = inspect_catalog(args.catalog, include_private=bool(args.local_manifest))
        _write_atomic(args.report, report)
        if args.local_manifest is not None and private is not None:
            _write_atomic(args.local_manifest, private)
    except (sqlite3.Error, OSError, CatalogIntakeError, ValueError) as exc:
        cli.exit(2, f"RAW Catalog Intake FAILED (no source changes): {exc}\n")
    print("Aggregate report:", args.report)
    print("RAW scanned:", report["totals"].get("catalog_raw_records", 0))
    print("Develop parsed:", report["totals"].get("parsed_raw_records", 0))
    print("Candidate groups:", report["candidate_folder_day_groups"])
    print("Training-ready samples: 0 (requires approved original RAW and event/finality validation)")
    if args.local_manifest:
        print("Local PRIVATE manifest (do not upload):", args.local_manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
