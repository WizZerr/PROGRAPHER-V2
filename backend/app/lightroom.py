from __future__ import annotations

import os
import json
import hashlib
import re
import shutil
import sqlite3
import tempfile
import zlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

LIGHTROOM_SKIP_DIRS = {
    "AppData", "$Recycle.Bin", "System Volume Information", "node_modules",
    ".git", ".next", ".venv", "venv", "Windows", "Program Files",
    "Program Files (x86)",
}

LIGHTROOM_DEVELOP_KEYS = {
    "exposure": ["Exposure2012", "Exposure"],
    "contrast": ["Contrast2012", "Contrast"],
    "highlights": ["Highlights2012", "Highlights"],
    "shadows": ["Shadows2012", "Shadows"],
    "whites": ["Whites2012", "Whites"],
    "blacks": ["Blacks2012", "Blacks"],
    "temperature": ["Temperature"],
    "tint": ["Tint"],
    "clarity": ["Clarity2012", "Clarity"],
    "texture": ["Texture"],
    "dehaze": ["Dehaze"],
    "vibrance": ["Vibrance"],
    "saturation": ["Saturation"],
    "tone_curve": ["ToneCurve", "ToneCurvePV2012"],
    "hsl": ["HueAdjustment", "SaturationAdjustment", "LuminanceAdjustment"],
    "crop": ["CropTop", "CropLeft", "CropRight", "CropBottom", "CropAngle"],
    "black_white": ["ConvertToGrayscale"],
    "process_version": ["ProcessVersion"],
    "masking": ["Mask", "Masking", "CorrectionMasks"],
}

RAW_EXTS = {
    "dng", "cr2", "cr3", "nef", "arw", "raf", "rw2", "orf", "pef",
    "srw", "3fr", "fff", "iiq", "rwl", "mos", "mrw", "nrw", "x3f",
}
JPEG_EXTS = {"jpg", "jpeg"}


class LightroomCatalogError(Exception):
    pass


def catalog_roots() -> list[tuple[str, Path]]:
    home = Path.home()
    candidates = [
        ("Lightroom", home / "Pictures" / "Lightroom"),
        ("Pictures", home / "Pictures"),
        ("Documents", home / "Documents"),
        ("Desktop", home / "Desktop"),
    ]

    userprofile = os.getenv("USERPROFILE")
    if userprofile:
        up = Path(userprofile)
        candidates += [
            ("Lightroom", up / "Pictures" / "Lightroom"),
            ("Pictures", up / "Pictures"),
            ("Documents", up / "Documents"),
            ("Desktop", up / "Desktop"),
        ]

    onedrive = os.getenv("OneDrive")
    if onedrive:
        od = Path(onedrive)
        candidates += [
            ("OneDrive Pictures", od / "Pictures"),
            ("OneDrive Documents", od / "Documents"),
            ("OneDrive Desktop", od / "Desktop"),
        ]

    seen, out = set(), []
    for label, path in candidates:
        try:
            p = path.expanduser().resolve()
        except Exception:
            continue
        key = str(p).lower()
        if key in seen or not p.exists() or not p.is_dir():
            continue
        seen.add(key)
        out.append((label, p))
    return out


def _catalog_card(path: Path, source: str) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path),
        "source": source,
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "modified_at": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(timespec="seconds"),
        "has_lrcat_data": path.with_suffix(".lrcat-data").exists(),
        "has_wal": Path(str(path) + "-wal").exists(),
    }


def scan_catalogs(max_depth: int = 5, max_catalogs: int = 100) -> list[dict]:
    found: dict[str, dict] = {}
    for label, root in catalog_roots():
        root_depth = len(root.parts)
        for current, dirs, files in os.walk(root):
            depth = len(Path(current).parts) - root_depth
            dirs[:] = [
                d for d in dirs
                if d not in LIGHTROOM_SKIP_DIRS
                and not d.startswith(".")
                and depth < max_depth
            ]
            for filename in files:
                if not filename.lower().endswith(".lrcat"):
                    continue
                path = Path(current) / filename
                try:
                    card = _catalog_card(path, label)
                    found[card["path"].lower()] = card
                except Exception:
                    pass
                if len(found) >= max_catalogs:
                    break
            if len(found) >= max_catalogs:
                break
        if len(found) >= max_catalogs:
            break
    return sorted(found.values(), key=lambda x: x["modified_at"], reverse=True)


def _cols(conn: sqlite3.Connection, table: str) -> list[str]:
    safe = table.replace('"', '""')
    return [r["name"] for r in conn.execute(f'PRAGMA table_info("{safe}")').fetchall()]


def _count(conn: sqlite3.Connection, table: str) -> Optional[int]:
    try:
        safe = table.replace('"', '""')
        return int(conn.execute(f'SELECT COUNT(*) c FROM "{safe}"').fetchone()["c"])
    except Exception:
        return None


def _find_col(columns: list[str], candidates: list[str]) -> Optional[str]:
    lower = {c.lower(): c for c in columns}
    for item in candidates:
        if item.lower() in lower:
            return lower[item.lower()]
    return None


def _file_types(conn: sqlite3.Connection, tables: set[str]) -> dict:
    result = {
        "raw": 0,
        "jpeg": 0,
        "other": 0,
        "total_with_extension": 0,
        "breakdown": {},
    }
    if "AgLibraryFile" not in tables:
        return result

    columns = _cols(conn, "AgLibraryFile")
    extension = _find_col(columns, ["extension", "fileExtension"])
    if not extension:
        return result

    safe_ext = extension.replace('"', '""')
    sql = (
        f'SELECT LOWER(COALESCE("{safe_ext}", \'\')) ext, COUNT(*) c '
        f'FROM "AgLibraryFile" GROUP BY LOWER(COALESCE("{safe_ext}", \'\'))'
    )

    for row in conn.execute(sql).fetchall():
        ext = (row["ext"] or "").lstrip(".")
        count = int(row["c"] or 0)
        result["breakdown"][ext or "(none)"] = count
        result["total_with_extension"] += count
        if ext in RAW_EXTS:
            result["raw"] += count
        elif ext in JPEG_EXTS:
            result["jpeg"] += count
        else:
            result["other"] += count
    return result


def _image_structure(conn: sqlite3.Connection, tables: set[str]) -> dict:
    result = {
        "image_records": 0,
        "source_photos": 0,
        "master_records": 0,
        "virtual_copies": 0,
        "edited_source_photos": 0,
        "edited_image_versions": 0,
        "copy_name_groups": [],
    }
    if "Adobe_images" not in tables:
        return result

    columns = _cols(conn, "Adobe_images")
    result["image_records"] = _count(conn, "Adobe_images") or 0

    root_col = _find_col(columns, ["rootFile"])
    master_col = _find_col(columns, ["masterImage"])
    copy_name_col = _find_col(columns, ["copyName"])
    develop_cache_col = _find_col(columns, ["developSettingsIDCache"])

    if root_col:
        safe_root = root_col.replace('"', '""')
        try:
            result["source_photos"] = int(
                conn.execute(
                    f'SELECT COUNT(DISTINCT "{safe_root}") c FROM "Adobe_images" '
                    f'WHERE "{safe_root}" IS NOT NULL AND "{safe_root}" != 0'
                ).fetchone()["c"]
            )
        except Exception:
            pass

    if master_col:
        safe_master = master_col.replace('"', '""')
        try:
            result["master_records"] = int(
                conn.execute(
                    f'SELECT COUNT(*) c FROM "Adobe_images" '
                    f'WHERE "{safe_master}" IS NULL OR "{safe_master}" = 0'
                ).fetchone()["c"]
            )
            result["virtual_copies"] = max(
                0, result["image_records"] - result["master_records"]
            )
        except Exception:
            pass
    else:
        # Even older catalogs can be estimated by one master per physical source file.
        result["master_records"] = result["source_photos"]
        result["virtual_copies"] = max(
            0, result["image_records"] - result["source_photos"]
        )

    # Prefer the final Develop Settings table over history rows.
    if "Adobe_imageDevelopSettings" in tables:
        ds_cols = _cols(conn, "Adobe_imageDevelopSettings")
        ds_image = _find_col(ds_cols, ["image"])
        image_id = _find_col(columns, ["id_local", "id"])
        if ds_image and image_id and root_col:
            safe_ds_image = ds_image.replace('"', '""')
            safe_image_id = image_id.replace('"', '""')
            safe_root = root_col.replace('"', '""')
            try:
                row = conn.execute(
                    f'''SELECT COUNT(DISTINCT ai."{safe_image_id}") versions,
                               COUNT(DISTINCT ai."{safe_root}") sources
                        FROM "Adobe_images" ai
                        JOIN "Adobe_imageDevelopSettings" ds
                          ON ds."{safe_ds_image}" = ai."{safe_image_id}"'''
                ).fetchone()
                result["edited_image_versions"] = int(row["versions"] or 0)
                result["edited_source_photos"] = int(row["sources"] or 0)
            except Exception:
                pass

    if result["edited_source_photos"] == 0 and develop_cache_col and root_col:
        safe_dev = develop_cache_col.replace('"', '""')
        safe_root = root_col.replace('"', '""')
        try:
            row = conn.execute(
                f'''SELECT COUNT(*) versions, COUNT(DISTINCT "{safe_root}") sources
                    FROM "Adobe_images"
                    WHERE "{safe_dev}" IS NOT NULL AND "{safe_dev}" != 0'''
            ).fetchone()
            result["edited_image_versions"] = int(row["versions"] or 0)
            result["edited_source_photos"] = int(row["sources"] or 0)
        except Exception:
            pass

    if copy_name_col:
        safe_copy = copy_name_col.replace('"', '""')
        try:
            rows = conn.execute(
                f'''SELECT TRIM("{safe_copy}") name, COUNT(*) c
                    FROM "Adobe_images"
                    WHERE "{safe_copy}" IS NOT NULL AND TRIM("{safe_copy}") != ''
                    GROUP BY TRIM("{safe_copy}")
                    ORDER BY c DESC, name COLLATE NOCASE
                    LIMIT 100'''
            ).fetchall()
            result["copy_name_groups"] = [
                {"name": str(r["name"]), "photo_count": int(r["c"] or 0)}
                for r in rows
            ]
        except Exception:
            pass

    return result


def _collections(conn: sqlite3.Connection, tables: set[str]) -> list[dict]:
    if "AgLibraryCollection" not in tables:
        return []

    table = "AgLibraryCollection"
    columns = _cols(conn, table)
    id_col = _find_col(columns, ["id_local", "id"])
    name_col = _find_col(columns, ["name", "title"])
    parent_col = _find_col(columns, ["parent", "parentId"])
    creation_col = _find_col(columns, ["creationId"])
    image_count_col = _find_col(columns, ["imageCount"])

    if not id_col or not name_col:
        return []

    safe_id = id_col.replace('"', '""')
    safe_name = name_col.replace('"', '""')
    select_parts = [
        f'"{safe_id}" collection_id',
        f'"{safe_name}" collection_name',
    ]
    if parent_col:
        select_parts.append(f'"{parent_col.replace(chr(34), chr(34)*2)}" parent_id')
    else:
        select_parts.append('NULL parent_id')
    if creation_col:
        select_parts.append(f'"{creation_col.replace(chr(34), chr(34)*2)}" creation_id')
    else:
        select_parts.append("'' creation_id")
    if image_count_col:
        select_parts.append(f'"{image_count_col.replace(chr(34), chr(34)*2)}" stored_image_count')
    else:
        select_parts.append('NULL stored_image_count')

    rows = conn.execute(
        f'''SELECT {", ".join(select_parts)}
            FROM "{table}"
            WHERE "{safe_name}" IS NOT NULL
            ORDER BY "{safe_name}" COLLATE NOCASE'''
    ).fetchall()

    membership_counts: dict[str, int] = {}
    if "AgLibraryCollectionImage" in tables:
        ci_cols = _cols(conn, "AgLibraryCollectionImage")
        collection_fk = _find_col(ci_cols, ["collection"])
        image_fk = _find_col(ci_cols, ["image"])
        if collection_fk:
            safe_fk = collection_fk.replace('"', '""')
            try:
                count_rows = conn.execute(
                    f'''SELECT "{safe_fk}" collection_id, COUNT(*) c
                        FROM "AgLibraryCollectionImage"
                        GROUP BY "{safe_fk}"'''
                ).fetchall()
                membership_counts = {
                    str(r["collection_id"]): int(r["c"] or 0)
                    for r in count_rows
                }
            except Exception:
                pass

    raw = {}
    for row in rows:
        cid = str(row["collection_id"])
        creation_id = str(row["creation_id"] or "")
        name = str(row["collection_name"])
        parent = row["parent_id"]
        stored = row["stored_image_count"]
        count = membership_counts.get(cid)
        if count is None and stored not in (None, ""):
            try:
                count = int(stored)
            except Exception:
                count = None

        is_group = "group" in creation_id.lower()
        is_smart = "smart" in creation_id.lower()
        is_system = any(
            token in creation_id.lower()
            for token in ["quick", "system", "temporary"]
        ) or name.lower() in {
            "quick collection", "past month", "recently modified",
            "without keywords", "not in collection", "smart collections",
        }

        raw[cid] = {
            "id": cid,
            "name": name,
            "parent_id": str(parent) if parent not in (None, "") else None,
            "photo_count": count,
            "source_table": table,
            "creation_id": creation_id,
            "is_group": is_group,
            "is_smart": is_smart,
            "is_system": is_system,
        }

    def build_path(cid: str) -> tuple[str, int]:
        parts = []
        current = raw.get(cid)
        seen = set()
        depth = 0
        while current and current["id"] not in seen and depth < 30:
            seen.add(current["id"])
            parts.append(current["name"])
            parent_id = current.get("parent_id")
            if not parent_id:
                break
            current = raw.get(parent_id)
            depth += 1
        parts.reverse()
        return " / ".join(parts), max(0, len(parts) - 1)

    result = []
    for cid, item in raw.items():
        path, depth = build_path(cid)
        photo_count = item.get("photo_count")
        # A collection is a useful training candidate when it is not a group/system
        # and actually contains a meaningful number of image records.
        recommended = (
            not item["is_group"]
            and not item["is_system"]
            and isinstance(photo_count, int)
            and photo_count >= 50
        )
        result.append({
            **item,
            "path": path,
            "depth": depth,
            "recommended": recommended,
        })

    result.sort(
        key=lambda x: (
            not x["recommended"],
            x["is_system"],
            -(x["photo_count"] or 0),
            x["path"].lower(),
        )
    )
    return result


def _develop(conn: sqlite3.Connection, tables: set[str]) -> dict:
    develop_tables = [
        t for t in tables
        if any(token in t.lower() for token in ["develop", "history", "setting", "adjust"])
    ]
    details, chunks = [], []

    for table in develop_tables[:30]:
        columns = _cols(conn, table)
        details.append({"table": table, "row_count": _count(conn, table), "columns": columns})
        safe = table.replace('"', '""')
        try:
            cursor = conn.execute(f'SELECT * FROM "{safe}" LIMIT 20')
            names = [d[0] for d in cursor.description]
            for row in cursor.fetchall():
                for _, value in zip(names, row):
                    if isinstance(value, bytes):
                        text = value.decode("utf-8", errors="ignore")
                    elif isinstance(value, str):
                        text = value
                    else:
                        continue
                    if text:
                        chunks.append(text[:150000])
        except Exception:
            pass

    combined = "\n".join(chunks).lower()
    capabilities = []
    for key, aliases in LIGHTROOM_DEVELOP_KEYS.items():
        found = any(alias.lower() in combined for alias in aliases)
        if not found:
            for detail in details:
                hay = " ".join(detail["columns"]).lower()
                if any(alias.lower() in hay for alias in aliases):
                    found = True
                    break
        if found:
            capabilities.append(key)

    final_settings_count = (
        _count(conn, "Adobe_imageDevelopSettings")
        if "Adobe_imageDevelopSettings" in tables
        else 0
    ) or 0
    history_count = (
        _count(conn, "Adobe_libraryImageDevelopHistoryStep")
        if "Adobe_libraryImageDevelopHistoryStep" in tables
        else 0
    ) or 0

    return {
        "develop_table_count": len(develop_tables),
        "develop_record_count": final_settings_count or history_count,
        "final_settings_count": final_settings_count,
        "history_step_count": history_count,
        "capabilities": capabilities,
        "tables": details,
    }


def _source_file_names(conn: sqlite3.Connection, tables: set[str]) -> list[str]:
    if "AgLibraryFile" not in tables:
        return []
    columns = _cols(conn, "AgLibraryFile")
    base = _find_col(columns, ["baseName"])
    ext = _find_col(columns, ["extension"])
    idx = _find_col(columns, ["idx_filename", "lc_idx_filename", "originalFilename"])

    names = []
    try:
        if base and ext:
            safe_base = base.replace('"', '""')
            safe_ext = ext.replace('"', '""')
            rows = conn.execute(
                f'''SELECT "{safe_base}" base_name, "{safe_ext}" ext
                    FROM "AgLibraryFile"'''
            ).fetchall()
            for row in rows:
                base_name = str(row["base_name"] or "").strip()
                extension = str(row["ext"] or "").strip().lstrip(".")
                if base_name:
                    names.append(base_name + (f".{extension}" if extension else ""))
        elif idx:
            safe_idx = idx.replace('"', '""')
            rows = conn.execute(
                f'SELECT "{safe_idx}" filename FROM "AgLibraryFile"'
            ).fetchall()
            names = [str(r["filename"] or "").strip() for r in rows if r["filename"]]
    except Exception:
        return []
    return names


def _nearby_source_availability(source: Path, expected_names: list[str]) -> dict:
    if not expected_names:
        return {"matched": 0, "total": 0, "percent": 0, "method": "none"}

    expected_counter = Counter(name.lower() for name in expected_names if name)
    total = sum(expected_counter.values())
    if total == 0:
        return {"matched": 0, "total": 0, "percent": 0, "method": "none"}

    roots = [source.parent]
    if source.parent.parent.exists():
        roots.append(source.parent.parent)

    actual = Counter()
    visited_dirs = 0
    max_dirs = 250
    max_depth = 3

    for root in roots:
        root_depth = len(root.parts)
        try:
            for current, dirs, files in os.walk(root):
                visited_dirs += 1
                depth = len(Path(current).parts) - root_depth
                dirs[:] = [
                    d for d in dirs
                    if d not in LIGHTROOM_SKIP_DIRS
                    and not d.startswith(".")
                    and depth < max_depth
                ]
                for filename in files:
                    key = filename.lower()
                    if key in expected_counter:
                        actual[key] += 1
                if visited_dirs >= max_dirs:
                    break
        except Exception:
            continue
        if visited_dirs >= max_dirs:
            break

    matched = sum(min(expected_counter[k], actual[k]) for k in expected_counter)
    percent = round((matched / total) * 100, 1) if total else 0
    return {
        "matched": matched,
        "total": total,
        "percent": percent,
        "method": "near_catalog_filename_match",
    }



def _technical_group_reason(name: str) -> Optional[str]:
    """
    Detect Lightroom / dataset plumbing names that should never be presented
    to a normal photographer as an editing style.
    """
    compact = " ".join((name or "").strip().split())
    lower = compact.lower()

    hard_patterns = [
        (r"^copy[\s_-]*\d+$", "virtual_copy_sequence"),
        (r"^virtual[\s_-]*copy\b", "virtual_copy"),
        (r"^input\b", "input_variant"),
        (r"^inputas", "input_variant"),
        (r"\bas[\s_-]*shot\b", "as_shot_baseline"),
        (r"\bzeroed\b", "zeroed_baseline"),
        (r"^original$", "original"),
        (r"^master$", "master"),
        (r"\bdefault\b", "default_variant"),
        (r"^lr\d*auto", "lightroom_auto_variant"),
        (r"\bautowith\b", "lightroom_auto_variant"),
        (r"\bwhite[\s_-]*balance\b", "white_balance_test"),
        (r"\bwhitebalance\b", "white_balance_test"),
        (r"\bminus[\s_-]*\d", "parameter_test_variant"),
        (r"\bplus[\s_-]*\d", "parameter_test_variant"),
    ]
    for pattern, reason in hard_patterns:
        if re.search(pattern, lower, flags=re.I):
            return reason

    return None


def _style_group_score(
    name: str,
    photo_count: int,
    source_count: int,
    kind: str,
) -> tuple[int, float, Optional[str]]:
    """
    Generic confidence score for whether a Lightroom group represents a
    photographer-facing style / body of edited work rather than technical
    catalog plumbing.
    """
    technical_reason = _technical_group_reason(name)
    coverage = (
        (photo_count / source_count) * 100.0
        if source_count > 0 and photo_count > 0
        else 0.0
    )

    if technical_reason:
        return 0, round(coverage, 1), technical_reason

    score = 35

    if photo_count >= 50:
        score += 10
    if photo_count >= 500:
        score += 8
    if photo_count >= 2500:
        score += 7

    if coverage >= 90:
        score += 20
    elif coverage >= 50:
        score += 15
    elif coverage >= 20:
        score += 10
    elif coverage >= 5:
        score += 5

    compact = " ".join((name or "").strip().split())
    lower = compact.lower()

    # Very compact variant labels (A/B/C, Warm, Clean...) can be legitimate
    # full-catalog styles. FiveK happens to use A-E, but this rule is generic.
    if re.fullmatch(r"[A-Za-z]", compact):
        score += 18
    if "expert" in lower:
        score += 18

    if kind == "collection":
        score += 8

    # Penalize names that look machine-generated even when they did not hit a
    # hard technical rule.
    if len(compact) > 70:
        score -= 8
    if re.search(r"\b(test|tmp|temp|debug)\b", lower):
        score -= 18

    return max(0, min(100, score)), round(coverage, 1), None


def _friendly_training_groups(
    collections: list[dict],
    copy_name_groups: list[dict],
    source_count: int,
) -> tuple[list[dict], dict]:
    """
    V16.2 Smart Style Discovery.

    Build all plausible groups, classify them, hide technical Lightroom
    artifacts, and return only photographer-facing style candidates.
    """
    raw_groups: list[dict] = []
    seen_names: set[str] = set()

    # User-created Lightroom Collections are strong evidence, but still pass
    # through technical-name filtering because research catalogs can contain
    # utility collections.
    for collection in collections:
        if collection.get("is_group") or collection.get("is_system"):
            continue
        count = collection.get("photo_count")
        if not isinstance(count, int) or count <= 0:
            continue

        name = str(collection.get("name") or "").strip()
        if not name:
            continue

        key_name = name.casefold()
        if key_name in seen_names:
            continue
        seen_names.add(key_name)

        raw_groups.append({
            "id": str(collection["id"]),
            "name": name,
            "path": collection.get("path") or name,
            "photo_count": count,
            "kind": "collection",
        })

    # Virtual-copy labels can represent full alternate editing styles. They
    # can also be technical junk ("Copy 1", "Input ..."), which is exactly
    # what Smart Style Discovery filters automatically.
    for idx, group in enumerate(copy_name_groups):
        name = str(group.get("name") or "").strip()
        count = int(group.get("photo_count") or 0)
        if not name or count <= 0:
            continue

        key_name = name.casefold()
        if key_name in seen_names:
            continue
        seen_names.add(key_name)

        raw_groups.append({
            "id": f"copy-name:{idx}:{name}",
            "name": name,
            "path": name,
            "photo_count": count,
            "kind": "virtual_copy_group",
        })

    candidates: list[dict] = []
    technical_groups: list[dict] = []

    for group in raw_groups:
        score, coverage, technical_reason = _style_group_score(
            group["name"],
            group["photo_count"],
            source_count,
            group["kind"],
        )

        enriched = {
            **group,
            "style_score": score,
            "coverage_percent": coverage,
            "technical": bool(technical_reason),
            "technical_reason": technical_reason,
        }

        if technical_reason:
            technical_groups.append(enriched)
            continue

        # Require enough evidence to call something a style candidate.
        if group["photo_count"] >= 50 and score >= 55:
            display_name = group["name"]
            if re.fullmatch(r"[A-Za-z]", display_name):
                display_name = f"סגנון {display_name.upper()}"

            candidates.append({
                **enriched,
                "display_name": display_name,
                "recommended": False,
                "badge_he": "מתאים ללמידה",
            })

    candidates.sort(
        key=lambda x: (
            -x["style_score"],
            -x["photo_count"],
            x["name"].casefold(),
        )
    )

    # Determine if the visible groups are mutually-exclusive style variants.
    # If multiple candidates each cover almost the full set of source photos,
    # they are alternate renditions of the same material and the user should
    # choose ONE style, not combine them.
    full_coverage = [
        g for g in candidates
        if source_count > 0 and g["coverage_percent"] >= 80
    ]
    if len(full_coverage) >= 2 and len(full_coverage) >= max(2, int(len(candidates) * 0.6)):
        mode = "style_variants"
        selection_mode = "single"
    elif candidates:
        mode = "collections"
        selection_mode = "multiple"
    else:
        mode = "whole_catalog"
        selection_mode = "none"

    recommended_id = None
    if len(candidates) == 1:
        recommended_id = candidates[0]["id"]
    elif len(candidates) >= 2:
        first, second = candidates[0], candidates[1]
        if first["style_score"] >= 82 and first["style_score"] >= second["style_score"] + 12:
            recommended_id = first["id"]

    if recommended_id:
        for group in candidates:
            if group["id"] == recommended_id:
                group["recommended"] = True
                group["badge_he"] = "מומלץ"
                break

    if mode == "style_variants":
        title_he = f"זיהינו {len(candidates)} סגנונות עריכה"
        description_he = "ProGrapher סינן גרסאות טכניות והשאיר רק סגנונות עריכה אמיתיים לבחירה."
    elif mode == "collections":
        title_he = f"מצאנו {len(candidates)} קבוצות שמתאימות ללמידה"
        description_he = "ProGrapher סינן אוטומטית קבוצות מערכת וגרסאות טכניות."
    else:
        title_he = "הקטלוג מוכן ללמידה"
        description_he = "לא צריך לבחור קבוצה. ProGrapher ישתמש בחומר העריכה המתאים שמצא."

    discovery = {
        "mode": mode,
        "selection_mode": selection_mode,
        "candidate_count": len(candidates),
        "technical_group_count": len(technical_groups),
        "raw_group_count": len(raw_groups),
        "recommended_id": recommended_id,
        "auto_selected_id": recommended_id if len(candidates) == 1 else None,
        "title_he": title_he,
        "description_he": description_he,
        # Kept for developer diagnostics; the normal V16.2 UI never renders it.
        "technical_groups": technical_groups,
    }

    return candidates, discovery

def _readiness(
    source_count: int,
    edited_source_count: int,
    file_availability: dict,
    training_groups: list[dict],
    develop: dict,
) -> dict:
    if source_count <= 0:
        return {
            "state": "needs_attention",
            "score": 0,
            "message_he": "לא הצלחנו לזהות תמונות מקור בקטלוג הזה.",
        }

    edit_coverage = min(1.0, edited_source_count / source_count) if source_count else 0.0
    file_coverage = (
        min(1.0, file_availability.get("matched", 0) / source_count)
        if source_count else 0.0
    )
    has_develop = bool(develop.get("capabilities")) or bool(develop.get("develop_record_count"))
    has_groups = any(group.get("recommended") for group in training_groups)

    score = round(
        100 * (
            0.42 * edit_coverage
            + 0.30 * file_coverage
            + 0.18 * (1.0 if has_develop else 0.0)
            + 0.10 * (1.0 if has_groups else 0.0)
        )
    )

    if score >= 85:
        state = "ready"
        message = "הקטלוג נראה מצוין לבניית פרופיל AI מקצועי."
    elif score >= 60:
        state = "good"
        message = "מצאנו מספיק מידע כדי להתקדם, ויש כמה פרטים שנבדוק בזמן בניית ה־Dataset."
    else:
        state = "needs_attention"
        message = "מצאנו את הקטלוג, אבל חסר חלק מהמידע שנרצה ללמידה מלאה."

    return {"state": state, "score": score, "message_he": message}


def analyze_catalog(catalog_path: str) -> dict:
    source = Path(catalog_path).expanduser()
    try:
        source = source.resolve()
    except Exception:
        pass

    if not source.exists() or not source.is_file():
        raise LightroomCatalogError("קטלוג Lightroom לא נמצא")
    if source.suffix.lower() != ".lrcat":
        raise LightroomCatalogError("יש לבחור קובץ Lightroom Classic מסוג .lrcat")

    with tempfile.TemporaryDirectory(prefix="prographer_lrcat_") as temp_dir:
        copied = Path(temp_dir) / source.name
        shutil.copy2(source, copied)
        for suffix in ("-wal", "-shm"):
            companion = Path(str(source) + suffix)
            if companion.exists():
                try:
                    shutil.copy2(companion, Path(str(copied) + suffix))
                except Exception:
                    pass

        try:
            conn = sqlite3.connect(f"file:{copied.as_posix()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
        except sqlite3.DatabaseError as exc:
            raise LightroomCatalogError(
                f"לא ניתן לפתוח את הקטלוג כ-Lightroom SQLite: {exc}"
            ) from exc

        try:
            objects = conn.execute(
                "SELECT type,name FROM sqlite_master "
                "WHERE type IN ('table','view') ORDER BY type,name"
            ).fetchall()
            tables = {r["name"] for r in objects if r["type"] == "table"}

            file_count = _count(conn, "AgLibraryFile") if "AgLibraryFile" in tables else 0
            file_types = _file_types(conn, tables)
            image_structure = _image_structure(conn, tables)
            collections = _collections(conn, tables)
            develop = _develop(conn, tables)
            expected_names = _source_file_names(conn, tables)
            file_availability = _nearby_source_availability(source, expected_names)

            source_count = (
                image_structure.get("source_photos")
                or file_count
                or file_types.get("total_with_extension")
                or 0
            )
            edited_source_count = image_structure.get("edited_source_photos") or 0

            training_groups, style_discovery = _friendly_training_groups(
                collections,
                image_structure.get("copy_name_groups") or [],
                source_count,
            )
            recommended_group_count = sum(
                1 for group in training_groups if group.get("recommended")
            )
            readiness = _readiness(
                source_count,
                edited_source_count,
                file_availability,
                training_groups,
                develop,
            )

            candidate_tables = []
            for table in sorted(tables):
                lower = table.lower()
                if any(
                    token in lower
                    for token in [
                        "image", "photo", "file", "folder", "develop",
                        "history", "collection", "metadata", "keyword",
                    ]
                ):
                    candidate_tables.append({
                        "table": table,
                        "row_count": _count(conn, table),
                        "columns": _cols(conn, table)[:100],
                    })

            stat = source.stat()
            return {
                "ok": True,
                "catalog": {
                    "name": source.name,
                    "path": str(source),
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(timespec="seconds"),
                    "has_lrcat_data": source.with_suffix(".lrcat-data").exists(),
                },
                # User-facing summary. Physical/source photos are deliberately
                # separated from Lightroom's internal image/version records.
                "summary": {
                    "source_photo_count": int(source_count),
                    "edited_source_photo_count": int(edited_source_count),
                    "raw_count": file_types["raw"],
                    "jpeg_count": file_types["jpeg"],
                    "training_group_count": len(training_groups),
                    "style_candidate_count": len(training_groups),
                    "recommended_group_count": recommended_group_count,
                    "technical_group_count": int(style_discovery.get("technical_group_count") or 0),
                    "files_available_count": int(file_availability.get("matched", 0)),
                    "files_available_percent": float(file_availability.get("percent", 0)),
                    # Backward-compatible fields for V16 clients.
                    "image_count": int(source_count),
                    "file_count": int(file_count or 0),
                    "other_count": file_types["other"],
                    "collection_count": len(collections),
                    "develop_record_count": int(develop.get("develop_record_count") or 0),
                    "develop_table_count": int(develop.get("develop_table_count") or 0),
                },
                "training_groups": training_groups,
                "style_discovery": style_discovery,
                "readiness": readiness,
                "file_availability": file_availability,
                "file_types": file_types,
                "collections": collections,
                "develop": develop,
                # Diagnostics stay available to us / future developer UI, but
                # V16.1 intentionally does not expose them to the photographer.
                "diagnostics": {
                    "image_structure": image_structure,
                    "style_discovery": style_discovery,
                    "candidate_tables": candidate_tables[:80],
                    "schema": {
                        "table_count": len(tables),
                        "view_count": sum(1 for r in objects if r["type"] == "view"),
                    },
                },
                # Backward compatibility for old UI/debug clients.
                "candidate_tables": candidate_tables[:80],
                "schema": {
                    "table_count": len(tables),
                    "view_count": sum(1 for r in objects if r["type"] == "view"),
                },
            }
        finally:
            conn.close()
# =========================================================
# V16.3 / Backend V1.3.3 — Automatic Lightroom Dataset Builder
# =========================================================

DEVELOP_RECIPE_ALIASES = {
    "exposure": ["Exposure2012", "Exposure"],
    "contrast": ["Contrast2012", "Contrast"],
    "highlights": ["Highlights2012", "Highlights"],
    "shadows": ["Shadows2012", "Shadows"],
    "whites": ["Whites2012", "Whites"],
    "blacks": ["Blacks2012", "Blacks"],
    "temperature": ["Temperature"],
    "tint": ["Tint"],
    "clarity": ["Clarity2012", "Clarity"],
    "texture": ["Texture"],
    "dehaze": ["Dehaze"],
    "vibrance": ["Vibrance"],
    "saturation": ["Saturation"],
    "process_version": ["ProcessVersion"],
    "convert_to_grayscale": ["ConvertToGrayscale"],
    "crop_top": ["CropTop"],
    "crop_left": ["CropLeft"],
    "crop_right": ["CropRight"],
    "crop_bottom": ["CropBottom"],
    "crop_angle": ["CropAngle"],
}


def _decode_develop_payload(value) -> str:
    """
    Decode Lightroom's serialized Develop settings.

    Depending on Lightroom/catalog generation, `text` may be plain text or a
    deflated blob. Some catalog blobs carry a 4-byte uncompressed-length prefix
    before the zlib stream.
    """
    if value is None:
        return ""

    raw_candidates = []
    if isinstance(value, bytes):
        raw_candidates.append(value)

        # Lightroom uses deflated payloads in a number of catalog fields.
        for candidate in (value, value[4:] if len(value) > 4 else b""):
            if not candidate:
                continue
            try:
                raw_candidates.insert(0, zlib.decompress(candidate))
            except Exception:
                pass

        for raw in raw_candidates:
            for encoding in ("utf-8", "utf-16", "latin-1"):
                try:
                    text = raw.decode(encoding)
                    if text.strip():
                        return text
                except Exception:
                    pass
        return value.decode("utf-8", errors="ignore")

    return str(value)


def _flatten_json_scalars(value, prefix: str = "", out: Optional[dict] = None) -> dict:
    out = out if out is not None else {}
    if isinstance(value, dict):
        for key, child in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten_json_scalars(child, next_prefix, out)
    elif isinstance(value, list):
        # Preserve arrays such as tone curves; they can be useful targets later.
        if prefix:
            out[prefix] = value
    elif prefix:
        out[prefix] = value
    return out


def _coerce_scalar(value: str):
    text = str(value).strip().strip('"').strip("'")
    lower = text.lower()
    if lower in {"true", "yes"}:
        return True
    if lower in {"false", "no"}:
        return False
    if lower in {"nil", "null", "none"}:
        return None
    try:
        if re.fullmatch(r"[-+]?\d+", text):
            return int(text)
        if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", text):
            return float(text)
    except Exception:
        pass
    return text


def _parse_develop_payload(value) -> tuple[dict, dict]:
    """
    Returns (normalized_recipe, all_scalar_settings).

    Lightroom catalog generations differ. Newer catalogs often have JSON in
    Adobe_imageDevelopSettings.text; older/research catalogs can contain
    serialized key/value text or XML/XMP-like values. We preserve a broad
    scalar map and normalize the controls ProGrapher already understands.
    """
    text = _decode_develop_payload(value).strip()
    if not text:
        return {}, {}

    scalars: dict = {}
    try:
        parsed = json.loads(text)
        scalars.update(_flatten_json_scalars(parsed))
    except Exception:
        pass

    # XML/XMP attributes: crs:Exposure2012="+0.35"
    for match in re.finditer(
        r'(?:\b|:)([A-Za-z][A-Za-z0-9_.:-]{1,80})\s*=\s*["\']([^"\']{0,500})["\']',
        text,
    ):
        scalars.setdefault(match.group(1), _coerce_scalar(match.group(2)))

    # Lua bracket-key syntax: ["Exposure2012"] = 0.35
    for match in re.finditer(
        r'\[\s*["\']([A-Za-z][A-Za-z0-9_.:-]{1,80})["\']\s*\]\s*=\s*'
        r'([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|true|false|nil|null|["\'][^"\']{0,300}["\'])',
        text,
        flags=re.I,
    ):
        scalars.setdefault(match.group(1), _coerce_scalar(match.group(2)))

    # Lua / simple serialized settings: Exposure2012 = 0.35
    for match in re.finditer(
        r'\b([A-Za-z][A-Za-z0-9_.:-]{1,80})\s*[=:]\s*'
        r'([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|true|false|nil|null)',
        text,
        flags=re.I,
    ):
        scalars.setdefault(match.group(1), _coerce_scalar(match.group(2)))

    # XML element values: <crs:Exposure2012>0.35</crs:Exposure2012>
    for match in re.finditer(
        r'<(?:[A-Za-z0-9_-]+:)?([A-Za-z][A-Za-z0-9_.-]{1,80})[^>]*>'
        r'\s*([^<>]{1,300})\s*</',
        text,
    ):
        scalars.setdefault(match.group(1), _coerce_scalar(match.group(2)))

    # Build a case-insensitive lookup on the last path component / namespace.
    lookup = {}
    for key, val in scalars.items():
        leaf = str(key).split('.')[-1].split(':')[-1]
        lookup.setdefault(leaf.casefold(), val)

    recipe = {}
    for normalized, aliases in DEVELOP_RECIPE_ALIASES.items():
        for alias in aliases:
            if alias.casefold() in lookup:
                recipe[normalized] = lookup[alias.casefold()]
                break

    return recipe, scalars


def _nearby_file_index(catalog_path: Path, wanted_names: set[str], progress=None) -> dict[str, str]:
    wanted = {name.casefold() for name in wanted_names if name}
    result: dict[str, str] = {}
    if not wanted:
        return result

    roots = [catalog_path.parent]
    parent = catalog_path.parent.parent
    if parent.exists() and parent not in roots:
        roots.append(parent)

    visited = 0
    max_dirs = 3000
    max_depth = 5
    for root in roots:
        root_depth = len(root.parts)
        try:
            for current, dirs, files in os.walk(root):
                visited += 1
                depth = len(Path(current).parts) - root_depth
                dirs[:] = [
                    d for d in dirs
                    if d not in LIGHTROOM_SKIP_DIRS
                    and not d.startswith('.')
                    and depth < max_depth
                ]
                for filename in files:
                    key = filename.casefold()
                    if key in wanted and key not in result:
                        result[key] = str((Path(current) / filename).resolve())
                if len(result) >= len(wanted) or visited >= max_dirs:
                    break
            if len(result) >= len(wanted) or visited >= max_dirs:
                break
        except Exception:
            continue
    if progress:
        progress("matching_files", 52, {"matched_files": len(result), "wanted_files": len(wanted)})
    return result


def _dataset_rows_for_group(conn: sqlite3.Connection, tables: set[str], group: dict) -> list[sqlite3.Row]:
    if "Adobe_images" not in tables or "AgLibraryFile" not in tables:
        raise LightroomCatalogError("הקטלוג לא מכיל את טבלאות התמונות הנדרשות לבניית Dataset")

    ai_cols = _cols(conn, "Adobe_images")
    fi_cols = _cols(conn, "AgLibraryFile")
    ai_id = _find_col(ai_cols, ["id_local", "id"])
    root_file = _find_col(ai_cols, ["rootFile"])
    copy_name = _find_col(ai_cols, ["copyName"])
    master_image = _find_col(ai_cols, ["masterImage"])
    fi_id = _find_col(fi_cols, ["id_local", "id"])
    base_name = _find_col(fi_cols, ["baseName"])
    extension = _find_col(fi_cols, ["extension"])
    folder_fk = _find_col(fi_cols, ["folder"])

    if not all([ai_id, root_file, fi_id, base_name, extension]):
        raise LightroomCatalogError("לא הצלחנו לזהות את קישורי התמונה/קובץ בקטלוג Lightroom")

    def col(alias: str, name: Optional[str], out_name: str, default="NULL"):
        if not name:
            return f"{default} AS {out_name}"
        safe = name.replace('"', '""')
        return f'{alias}."{safe}" AS {out_name}'

    select = [
        col("ai", ai_id, "image_id"),
        col("ai", root_file, "root_file_id"),
        col("ai", copy_name, "copy_name", "''"),
        col("ai", master_image, "master_image_id"),
        col("fi", fi_id, "file_id"),
        col("fi", base_name, "base_name", "''"),
        col("fi", extension, "extension", "''"),
    ]
    joins = [f'JOIN "AgLibraryFile" fi ON fi."{fi_id}" = ai."{root_file}"']

    # Folder/root path is useful for normal Lightroom catalogs. FiveK can be
    # relocated, so we still fall back to filename matching near the .lrcat.
    if folder_fk and "AgLibraryFolder" in tables:
        fo_cols = _cols(conn, "AgLibraryFolder")
        fo_id = _find_col(fo_cols, ["id_local", "id"])
        path_from_root = _find_col(fo_cols, ["pathFromRoot"])
        root_fk = _find_col(fo_cols, ["rootFolder"])
        if fo_id:
            joins.append(f'LEFT JOIN "AgLibraryFolder" fo ON fo."{fo_id}" = fi."{folder_fk}"')
            select.append(col("fo", path_from_root, "path_from_root", "''"))
            if root_fk and "AgLibraryRootFolder" in tables:
                rf_cols = _cols(conn, "AgLibraryRootFolder")
                rf_id = _find_col(rf_cols, ["id_local", "id"])
                absolute_path = _find_col(rf_cols, ["absolutePath"])
                if rf_id:
                    joins.append(f'LEFT JOIN "AgLibraryRootFolder" rf ON rf."{rf_id}" = fo."{root_fk}"')
                    select.append(col("rf", absolute_path, "absolute_root", "''"))
                else:
                    select.append("'' AS absolute_root")
            else:
                select.append("'' AS absolute_root")
        else:
            select.extend(["'' AS path_from_root", "'' AS absolute_root"])
    else:
        select.extend(["'' AS path_from_root", "'' AS absolute_root"])

    # Final Develop state. Lightroom's canonical link is normally
    # Adobe_images.developSettingsIDCache -> Adobe_imageDevelopSettings.id_local.
    # Some catalog generations can still be resolved through ds.image, so keep
    # that as a fallback instead of assuming one schema.
    has_develop = False
    develop_link_mode = "none"
    if "Adobe_imageDevelopSettings" in tables:
        ds_cols = _cols(conn, "Adobe_imageDevelopSettings")
        ds_id = _find_col(ds_cols, ["id_local", "id"])
        ds_image = _find_col(ds_cols, ["image"])
        ds_text = _find_col(ds_cols, ["text", "settings", "developSettings"])
        ai_develop_cache = _find_col(
            ai_cols,
            ["developSettingsIDCache", "developSettingsIdCache", "developSettings"],
        )

        if ai_develop_cache and ds_id:
            joins.append(
                f'LEFT JOIN "Adobe_imageDevelopSettings" ds '
                f'ON ds."{ds_id}" = ai."{ai_develop_cache}"'
            )
            select.append(col("ds", ds_text, "develop_payload", "NULL"))
            develop_link_mode = "developSettingsIDCache"
            has_develop = True
        elif ds_image:
            joins.append(
                f'LEFT JOIN "Adobe_imageDevelopSettings" ds '
                f'ON ds."{ds_image}" = ai."{ai_id}"'
            )
            select.append(col("ds", ds_text, "develop_payload", "NULL"))
            develop_link_mode = "image"
            has_develop = True

    if not has_develop:
        select.append("NULL AS develop_payload")

    select.append(f"'{develop_link_mode}' AS develop_link_mode")

    where = []
    params: list = []
    kind = str(group.get("kind") or "")
    group_id = str(group.get("id") or "")
    group_name = str(group.get("name") or "")

    if kind == "collection":
        if "AgLibraryCollectionImage" not in tables:
            raise LightroomCatalogError("לא נמצאה טבלת החברות ב-Collections")
        ci_cols = _cols(conn, "AgLibraryCollectionImage")
        ci_collection = _find_col(ci_cols, ["collection"])
        ci_image = _find_col(ci_cols, ["image"])
        if not ci_collection or not ci_image:
            raise LightroomCatalogError("מבנה ה-Collection בקטלוג אינו נתמך עדיין")
        joins.append(f'JOIN "AgLibraryCollectionImage" ci ON ci."{ci_image}" = ai."{ai_id}"')
        where.append(f'CAST(ci."{ci_collection}" AS TEXT) = ?')
        params.append(group_id)
    elif kind == "virtual_copy_group":
        if not copy_name:
            raise LightroomCatalogError("לא נמצאה עמודת Virtual Copy בקטלוג")
        where.append(f'TRIM(ai."{copy_name}") = ?')
        params.append(group_name)
    else:
        # Whole-catalog fallback: prefer image records that have final develop settings.
        if has_develop:
            where.append("ds.image IS NOT NULL")

    sql = "SELECT " + ", ".join(select) + ' FROM "Adobe_images" ai ' + " ".join(joins)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ai.\"%s\"" % ai_id.replace('"', '""')
    return conn.execute(sql, params).fetchall()


def _catalog_candidate_path(row: sqlite3.Row) -> Optional[Path]:
    try:
        root = str(row["absolute_root"] or "")
        rel = str(row["path_from_root"] or "")
        base = str(row["base_name"] or "")
        ext = str(row["extension"] or "").lstrip('.')
        filename = base + (f".{ext}" if ext else "")
        if not filename:
            return None
        candidate = Path(root) / rel / filename if root else Path(rel) / filename
        return candidate
    except Exception:
        return None


def _stable_split(samples: list[dict]) -> dict[str, list[dict]]:
    ordered = sorted(
        samples,
        key=lambda sample: hashlib.sha256(
            ("prographer-v16.3|" + str(sample.get("source_file_id")) + "|" + str(sample.get("filename"))).encode("utf-8")
        ).hexdigest(),
    )
    n = len(ordered)
    train_n = int(n * 0.80)
    val_n = int(n * 0.10)
    return {
        "train": ordered[:train_n],
        "validation": ordered[train_n:train_n + val_n],
        "test": ordered[train_n + val_n:],
    }


def build_training_dataset(
    catalog_path: str,
    group: dict,
    output_dir: Path,
    progress=None,
) -> dict:
    """
    Build a deterministic paired Lightroom dataset.

    This stage maps physical source files to one selected final Lightroom edit,
    extracts the final Develop payload/normalized recipe, validates the source
    file on disk, and writes locked train/validation/test splits.

    It does NOT train the recipe model and does NOT run the CLIP Vision Brain.
    Those consume this dataset in the next stage.
    """
    source = Path(catalog_path).expanduser()
    try:
        source = source.resolve()
    except Exception:
        pass
    if not source.exists():
        raise LightroomCatalogError("קטלוג Lightroom לא נמצא")

    def emit(stage: str, pct: int, detail: Optional[dict] = None):
        if progress:
            progress(stage, pct, detail or {})

    emit("safe_catalog_copy", 6, {})
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="prographer_dataset_") as td:
        copied = Path(td) / source.name
        shutil.copy2(source, copied)
        for suffix in ("-wal", "-shm"):
            companion = Path(str(source) + suffix)
            if companion.exists():
                try:
                    shutil.copy2(companion, Path(str(copied) + suffix))
                except Exception:
                    pass

        emit("reading_lightroom", 15, {})
        conn = sqlite3.connect(f"file:{copied.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            objects = conn.execute(
                "SELECT type,name FROM sqlite_master WHERE type IN ('table','view')"
            ).fetchall()
            tables = {r["name"] for r in objects if r["type"] == "table"}
            rows = _dataset_rows_for_group(conn, tables, group)
            emit("mapping_pairs", 30, {"target_records": len(rows)})

            # One target edit per physical source file. If a collection contains
            # duplicates, keep the first deterministic image record and report it.
            by_root: dict[str, sqlite3.Row] = {}
            duplicate_targets = 0
            for row in rows:
                key = str(row["root_file_id"] or row["file_id"] or row["image_id"])
                if key in by_root:
                    duplicate_targets += 1
                    continue
                by_root[key] = row

            unique_rows = list(by_root.values())
            wanted_names = set()
            for row in unique_rows:
                base = str(row["base_name"] or "").strip()
                ext = str(row["extension"] or "").strip().lstrip('.')
                if base:
                    wanted_names.add(base + (f".{ext}" if ext else ""))

            emit("matching_files", 40, {"unique_targets": len(unique_rows)})
            nearby = _nearby_file_index(source, wanted_names, progress=progress)

            samples = []
            missing_source = 0
            missing_develop = 0
            parsed_recipe_count = 0
            for idx, row in enumerate(unique_rows):
                base = str(row["base_name"] or "").strip()
                ext = str(row["extension"] or "").strip().lstrip('.')
                filename = base + (f".{ext}" if ext else "")

                candidate = _catalog_candidate_path(row)
                source_path = None
                if candidate and candidate.exists():
                    source_path = str(candidate.resolve())
                elif filename.casefold() in nearby:
                    source_path = nearby[filename.casefold()]

                payload = _decode_develop_payload(row["develop_payload"])
                recipe, settings = _parse_develop_payload(row["develop_payload"])
                if recipe:
                    parsed_recipe_count += 1
                if not payload:
                    missing_develop += 1
                if not source_path:
                    missing_source += 1

                sample = {
                    "sample_id": hashlib.sha256(
                        (str(row["root_file_id"]) + "|" + str(row["image_id"]) + "|" + group.get("name", "")).encode("utf-8")
                    ).hexdigest()[:24],
                    "source_file_id": row["root_file_id"],
                    "lightroom_image_id": row["image_id"],
                    "master_image_id": row["master_image_id"],
                    "filename": filename,
                    "source_path": source_path,
                    "source_exists": bool(source_path),
                    "target_style": {
                        "id": group.get("id"),
                        "name": group.get("name"),
                        "display_name": group.get("display_name") or group.get("name"),
                        "kind": group.get("kind"),
                    },
                    "lightroom_copy_name": row["copy_name"],
                    "develop_recipe": recipe,
                    "develop_settings": settings,
                    "develop_payload": payload,
                    "develop_payload_sha256": hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest() if payload else None,
                    "develop_link_mode": row["develop_link_mode"],
                    "pair_valid": bool(source_path and payload),
                }
                samples.append(sample)

                if idx and idx % 250 == 0:
                    pct = 55 + int(18 * (idx / max(1, len(unique_rows))))
                    emit("extracting_recipes", min(73, pct), {
                        "processed": idx,
                        "total": len(unique_rows),
                        "source_found": idx - missing_source,
                        "recipes_found": idx - missing_develop,
                    })

        finally:
            conn.close()

    emit("validating_pairs", 76, {})
    valid_samples = [sample for sample in samples if sample["pair_valid"]]

    # A zero-pair Dataset is a failed mapping, never a successful 100% build.
    # This prevents the UI from reporting "Dataset ready" when Lightroom's
    # Develop-settings relation was not resolved correctly.
    if not valid_samples:
        source_found = len(samples) - missing_source
        develop_found = len(samples) - missing_develop
        raise LightroomCatalogError(
            "לא נמצאה אף התאמה תקינה בין RAW לעריכת Lightroom. "
            f"קבצי מקור שנמצאו: {source_found}/{len(samples)}; "
            f"עריכות Lightroom שנמצאו: {develop_found}/{len(samples)}. "
            "ה-Dataset לא סומן כמוכן."
        )

    splits = _stable_split(valid_samples)

    emit("writing_dataset", 88, {
        "valid_pairs": len(valid_samples),
        "invalid_pairs": len(samples) - len(valid_samples),
    })

    def write_jsonl(path: Path, items: list[dict]):
        with path.open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")

    write_jsonl(output_dir / "all.jsonl", samples)
    write_jsonl(output_dir / "train.jsonl", splits["train"])
    write_jsonl(output_dir / "validation.jsonl", splits["validation"])
    write_jsonl(output_dir / "test.jsonl", splits["test"])

    manifest = {
        "dataset_version": "prographer-lightroom-v1",
        "catalog_path": str(source),
        "style": group,
        "target_records": len(rows),
        "unique_source_targets": len(unique_rows),
        "duplicate_targets_removed": duplicate_targets,
        "source_files_found": len(samples) - missing_source,
        "source_files_missing": missing_source,
        "develop_payloads_found": len(samples) - missing_develop,
        "develop_payloads_missing": missing_develop,
        "normalized_recipes_parsed": parsed_recipe_count,
        "develop_link_mode": (
            str(samples[0].get("develop_link_mode") or "")
            if samples else ""
        ),
        "valid_pairs": len(valid_samples),
        "invalid_pairs": len(samples) - len(valid_samples),
        "splits": {
            "train": len(splits["train"]),
            "validation": len(splits["validation"]),
            "test": len(splits["test"]),
        },
        "test_locked": True,
        "notes": {
            "vision_embeddings": "not_run_yet",
            "model_training": "not_run_yet",
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    emit("completed", 100, manifest)
    return manifest


# ================================================================
# V1.3.4 — Dataset Integrity Audit
# ================================================================

def _read_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    if not path.exists():
        raise LightroomCatalogError(f"קובץ Dataset חסר: {path.name}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception as exc:
                raise LightroomCatalogError(
                    f"JSONL לא תקין ב-{path.name}, שורה {line_number}"
                ) from exc
            if not isinstance(item, dict):
                raise LightroomCatalogError(
                    f"רשומת Dataset לא תקינה ב-{path.name}, שורה {line_number}"
                )
            items.append(item)
    return items


def _audit_check(key: str, label_he: str, passed: bool, *, detail_he: str = "", critical: bool = True, actual=None, expected=None) -> dict:
    return {
        "key": key,
        "label_he": label_he,
        "passed": bool(passed),
        "critical": bool(critical),
        "detail_he": detail_he,
        "actual": actual,
        "expected": expected,
    }


def _split_expected_ids(valid_samples: list[dict]) -> dict[str, set[str]]:
    splits = _stable_split(valid_samples)
    return {
        name: {str(item.get("sample_id") or "") for item in items}
        for name, items in splits.items()
    }


def audit_training_dataset(output_dir: Path, manifest: Optional[dict] = None, progress=None) -> dict:
    """
    Perform a strict, read-only integrity audit over a built Lightroom Dataset.

    The audit verifies one-to-one source/edit pairing, split isolation, selected
    style consistency, Develop payload/recipe availability, source files on
    disk and deterministic 80/10/10 membership. It never edits the Dataset.
    """
    output_dir = Path(output_dir)
    if not output_dir.exists():
        raise LightroomCatalogError("תיקיית ה-Dataset לא נמצאה")

    def emit(stage: str, pct: int, detail: Optional[dict] = None):
        if progress:
            progress(stage, pct, detail or {})

    if manifest is None:
        manifest_path = output_dir / "manifest.json"
        if not manifest_path.exists():
            raise LightroomCatalogError("manifest.json חסר")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    emit("reading_dataset", 12, {})
    all_items = _read_jsonl(output_dir / "all.jsonl")
    train = _read_jsonl(output_dir / "train.jsonl")
    validation = _read_jsonl(output_dir / "validation.jsonl")
    test = _read_jsonl(output_dir / "test.jsonl")

    valid = [item for item in all_items if item.get("pair_valid")]
    invalid = [item for item in all_items if not item.get("pair_valid")]
    emit("checking_pairs", 30, {"valid_pairs": len(valid), "invalid_pairs": len(invalid)})

    checks: list[dict] = []
    manifest_valid = int(manifest.get("valid_pairs") or 0)
    checks.append(_audit_check(
        "valid_pair_count", "מספר ההתאמות תואם ל-Manifest",
        len(valid) == manifest_valid and len(valid) > 0,
        detail_he=f"נמצאו {len(valid):,} זוגות תקינים.",
        actual=len(valid), expected=manifest_valid,
    ))

    sample_ids = [str(x.get("sample_id") or "") for x in valid]
    source_file_ids = [str(x.get("source_file_id")) if x.get("source_file_id") is not None else "" for x in valid]
    source_paths = [str(x.get("source_path") or "") for x in valid]
    target_ids = [str(x.get("lightroom_image_id")) if x.get("lightroom_image_id") is not None else "" for x in valid]

    checks.append(_audit_check(
        "unique_sample_ids", "לכל זוג יש מזהה ייחודי",
        bool(sample_ids) and all(sample_ids) and len(set(sample_ids)) == len(sample_ids),
        detail_he=f"{len(set(sample_ids)):,} מזהים ייחודיים מתוך {len(sample_ids):,}.",
        actual=len(set(sample_ids)), expected=len(sample_ids),
    ))
    checks.append(_audit_check(
        "unique_source_files", "כל תמונת מקור מופיעה פעם אחת בלבד",
        bool(source_file_ids) and all(source_file_ids) and len(set(source_file_ids)) == len(source_file_ids),
        detail_he=f"{len(set(source_file_ids)):,} קבצי מקור ייחודיים.",
        actual=len(set(source_file_ids)), expected=len(source_file_ids),
    ))
    checks.append(_audit_check(
        "unique_source_paths", "אין RAW כפולים ב-Dataset",
        bool(source_paths) and all(source_paths) and len(set(p.casefold() for p in source_paths)) == len(source_paths),
        detail_he=f"{len(set(p.casefold() for p in source_paths)):,} נתיבי מקור ייחודיים.",
        actual=len(set(p.casefold() for p in source_paths)), expected=len(source_paths),
    ))
    checks.append(_audit_check(
        "unique_target_edits", "כל עריכת Lightroom משויכת פעם אחת",
        bool(target_ids) and all(target_ids) and len(set(target_ids)) == len(target_ids),
        detail_he=f"{len(set(target_ids)):,} עריכות יעד ייחודיות.",
        actual=len(set(target_ids)), expected=len(target_ids),
    ))

    emit("checking_files", 48, {"checked": 0, "total": len(valid)})
    existing = 0
    nonempty = 0
    filename_match = 0
    total_valid = len(valid)
    for index, item in enumerate(valid, start=1):
        path_text = str(item.get("source_path") or "")
        path = Path(path_text) if path_text else None
        if path and path.exists() and path.is_file():
            existing += 1
            try:
                if path.stat().st_size > 0:
                    nonempty += 1
            except Exception:
                pass
            if path.name.casefold() == str(item.get("filename") or "").casefold():
                filename_match += 1

        if index == total_valid or index % 100 == 0:
            pct = 48
            if total_valid:
                pct = 48 + int((index / total_valid) * 13)
            emit(
                "checking_files",
                min(61, pct),
                {
                    "checked": index,
                    "total": total_valid,
                    "existing": existing,
                    "nonempty": nonempty,
                },
            )

    checks.append(_audit_check(
        "source_files_exist", "כל קבצי המקור עדיין קיימים במחשב",
        existing == len(valid),
        detail_he=f"{existing:,}/{len(valid):,} קבצים נמצאו.", actual=existing, expected=len(valid),
    ))
    checks.append(_audit_check(
        "source_files_nonempty", "קבצי המקור אינם ריקים",
        nonempty == len(valid),
        detail_he=f"{nonempty:,}/{len(valid):,} קבצים בגודל תקין.", actual=nonempty, expected=len(valid),
    ))
    checks.append(_audit_check(
        "filename_consistency", "שמות קבצי המקור תואמים לקטלוג",
        filename_match == len(valid),
        detail_he=f"{filename_match:,}/{len(valid):,} שמות תואמים.", actual=filename_match, expected=len(valid),
    ))

    emit("checking_recipes", 62, {})
    payload_count = sum(1 for x in valid if str(x.get("develop_payload") or "").strip())
    hash_count = sum(1 for x in valid if str(x.get("develop_payload_sha256") or "").strip())
    recipe_count = sum(1 for x in valid if isinstance(x.get("develop_recipe"), dict) and bool(x.get("develop_recipe")))
    checks.append(_audit_check(
        "develop_payloads", "לכל תמונה קיימת עריכת Lightroom מלאה",
        payload_count == len(valid),
        detail_he=f"{payload_count:,}/{len(valid):,} payloads קיימים.", actual=payload_count, expected=len(valid),
    ))
    checks.append(_audit_check(
        "develop_hashes", "כל עריכה קיבלה חתימת אימות",
        hash_count == len(valid),
        detail_he=f"{hash_count:,}/{len(valid):,} חתימות קיימות.", actual=hash_count, expected=len(valid),
    ))
    checks.append(_audit_check(
        "normalized_recipes", "כל עריכה פוענחה ל-Recipe שניתן ללמידה",
        recipe_count == len(valid),
        detail_he=f"{recipe_count:,}/{len(valid):,} Recipes פוענחו.", actual=recipe_count, expected=len(valid),
    ))

    # All valid records must represent the one style selected for this profile.
    style = manifest.get("style") or {}
    expected_style_id = str(style.get("id") or "")
    expected_style_name = str(style.get("name") or "")
    style_ids = {str((x.get("target_style") or {}).get("id") or "") for x in valid}
    style_names = {str((x.get("target_style") or {}).get("name") or "") for x in valid}
    style_consistent = len(style_ids) == 1 and len(style_names) == 1
    if expected_style_id:
        style_consistent = style_consistent and expected_style_id in style_ids
    if expected_style_name:
        style_consistent = style_consistent and expected_style_name in style_names
    checks.append(_audit_check(
        "style_consistency", "כל 5,000 הזוגות שייכים לסגנון שנבחר",
        style_consistent,
        detail_he=(f"הסגנון המאומת: {expected_style_name or next(iter(style_names), '—')}"),
        actual=sorted(style_names), expected=expected_style_name or None,
    ))

    # For virtual-copy style groups, make sure the actual Lightroom copy name
    # equals the selected style. This catches accidental C -> Copy N mappings.
    if str(style.get("kind") or "") == "virtual_copy_group" and expected_style_name:
        matching_copy_names = sum(
            1 for x in valid
            if str(x.get("lightroom_copy_name") or "").strip().casefold() == expected_style_name.strip().casefold()
        )
        checks.append(_audit_check(
            "virtual_copy_target", "העריכות מגיעות מה-Virtual Copy של הסגנון שנבחר",
            matching_copy_names == len(valid),
            detail_he=f"{matching_copy_names:,}/{len(valid):,} רשומות הן {expected_style_name}.",
            actual=matching_copy_names, expected=len(valid),
        ))

    emit("checking_splits", 78, {})
    split_items = {"train": train, "validation": validation, "test": test}
    split_ids = {name: {str(x.get("sample_id") or "") for x in items} for name, items in split_items.items()}
    split_counts = {name: len(items) for name, items in split_items.items()}
    manifest_splits = manifest.get("splits") or {}
    counts_match = all(split_counts[name] == int(manifest_splits.get(name) or 0) for name in split_items)
    checks.append(_audit_check(
        "split_counts", "Train / Validation / Test תואמים ל-Manifest",
        counts_match,
        detail_he=f"Train {len(train):,} · Validation {len(validation):,} · Test {len(test):,}.",
        actual=split_counts, expected=manifest_splits,
    ))

    overlap_tv = split_ids["train"] & split_ids["validation"]
    overlap_tt = split_ids["train"] & split_ids["test"]
    overlap_vt = split_ids["validation"] & split_ids["test"]
    overlap_total = len(overlap_tv | overlap_tt | overlap_vt)
    checks.append(_audit_check(
        "split_isolation", "אין דליפה בין Train / Validation / Test",
        overlap_total == 0,
        detail_he=f"נמצאו {overlap_total:,} מזהים חופפים.", actual=overlap_total, expected=0,
    ))

    valid_ids = set(sample_ids)
    split_union = split_ids["train"] | split_ids["validation"] | split_ids["test"]
    checks.append(_audit_check(
        "split_coverage", "כל הזוגות התקינים נמצאים בדיוק ב-Split אחד",
        split_union == valid_ids,
        detail_he=f"{len(split_union):,}/{len(valid_ids):,} זוגות מכוסים.", actual=len(split_union), expected=len(valid_ids),
    ))

    expected_ids = _split_expected_ids(valid)
    deterministic = all(split_ids[name] == expected_ids[name] for name in split_ids)
    checks.append(_audit_check(
        "deterministic_split", "החלוקה ניתנת לשחזור ואינה משתנה בין ריצות",
        deterministic,
        detail_he="ה-Split חושב מחדש ונמצא זהה." if deterministic else "ה-Split הנוכחי שונה מהחלוקה הדטרמיניסטית.",
    ))
    checks.append(_audit_check(
        "test_locked", "סט TEST מסומן כנעול מחוץ לאימון",
        bool(manifest.get("test_locked")),
        detail_he=f"{len(test):,} תמונות נשמרות לבדיקה סופית בלבד.", actual=bool(manifest.get("test_locked")), expected=True,
    ))

    emit("sampling", 90, {})
    # Deterministic audit preview: representative-looking records chosen by hash.
    preview_sorted = sorted(
        valid,
        key=lambda x: hashlib.sha256(("audit-v1|" + str(x.get("sample_id") or "")).encode("utf-8")).hexdigest(),
    )[:12]
    split_lookup = {}
    for split_name, items in split_items.items():
        for item in items:
            split_lookup[str(item.get("sample_id") or "")] = split_name

    preview = []
    for item in preview_sorted:
        recipe = item.get("develop_recipe") if isinstance(item.get("develop_recipe"), dict) else {}
        preview.append({
            "sample_id": item.get("sample_id"),
            "filename": item.get("filename"),
            "style": (item.get("target_style") or {}).get("display_name") or (item.get("target_style") or {}).get("name"),
            "split": split_lookup.get(str(item.get("sample_id") or "")),
            "source_file_id": item.get("source_file_id"),
            "lightroom_image_id": item.get("lightroom_image_id"),
            "lightroom_copy_name": item.get("lightroom_copy_name"),
            "develop_recipe": recipe,
        })

    critical = [check for check in checks if check.get("critical")]
    passed_critical = sum(1 for check in critical if check.get("passed"))
    score = round(100 * passed_critical / max(1, len(critical)))
    passed = bool(critical) and passed_critical == len(critical)

    result = {
        "audit_version": "prographer-dataset-audit-v1",
        "passed": passed,
        "integrity_percent": score,
        "checks_passed": passed_critical,
        "checks_total": len(critical),
        "checks": checks,
        "summary": {
            "total_records": len(all_items),
            "valid_pairs": len(valid),
            "invalid_pairs": len(invalid),
            "unique_source_files": len(set(source_file_ids)),
            "unique_target_edits": len(set(target_ids)),
            "normalized_recipes": recipe_count,
            "train": len(train),
            "validation": len(validation),
            "test": len(test),
            "split_overlap": overlap_total,
            "selected_style": expected_style_name or next(iter(style_names), ""),
        },
        "preview": preview,
    }
    emit("completed", 100, result)
    return result

