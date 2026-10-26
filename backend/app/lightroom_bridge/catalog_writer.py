"""LB-02: write Develop edits straight into a Lightroom Classic catalog while Lightroom is closed (as Imagen does).

Evidence (docs/LB_02_DIRECT_CATALOG_WRITE.md): on a test catalog (Lightroom Classic, schema 1504001, settings
Version 18.7, Windows, 25 RAWs from 5 makers) Lightroom showed every written slider and Custom white balance,
recomputed the real digest after we stored a new one, refreshed the thumbnails, kept crops, and listed a
"ProGrapher" History step. Writing only the settings text (old digest) left stale thumbnails, so a new digest,
historySettingsID and History step are always written together.

Safety: refuses while Lightroom has the catalog open, backs the catalog up before writing, validates every value
before touching anything, writes in one transaction, never changes keys other than the global sliders, leaves
photos the photographer edited alone unless asked, and restores the backup if SQLite reports damage afterwards.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

STEP_NAME = "ProGrapher"
COCOA_EPOCH = 978307200  # Lightroom stores times as seconds since 2001-01-01 UTC
# Global sliders ProGrapher may write: (minimum, maximum, decimals), Lightroom Develop key names (Process 2012+).
WRITABLE = {
    "Exposure2012": (-5.0, 5.0, 2), "Contrast2012": (-100, 100, 0), "Highlights2012": (-100, 100, 0),
    "Shadows2012": (-100, 100, 0), "Whites2012": (-100, 100, 0), "Blacks2012": (-100, 100, 0),
    "Texture": (-100, 100, 0), "Clarity2012": (-100, 100, 0), "Dehaze": (-100, 100, 0),
    "Vibrance": (-100, 100, 0), "Saturation": (-100, 100, 0),
    "Temperature": (2000, 50000, 0), "Tint": (-150, 150, 0),
}
WHITE_BALANCE = ("Temperature", "Tint")
NON_RAW = {"jpg", "jpeg", "tif", "tiff", "png", "heic", "heif", "psd", "avif"}
MIN_PROCESS_VERSION = 6.7  # Process 2012: the "...2012" slider names exist from here on
# History steps Lightroom adds without the photographer editing (English UI). Any other step name, including a
# localised "Import", marks the photo as edited, so unknown cases are protected rather than overwritten.
AUTOMATIC_STEPS = ("Import", "Export")
REQUIRED = {
    "Adobe_imageDevelopSettings": {"id_local", "image", "text", "digest", "historySettingsID",
                                   "hasDevelopAdjustmentsEx", "whiteBalance", "processVersion"},
    "Adobe_libraryImageDevelopHistoryStep": {"id_local", "id_global", "dateCreated", "digest", "hasBigData",
                                             "hasDevelopAdjustments", "image", "name", "relValueString",
                                             "text", "valueString"},
    "Adobe_images": {"id_local", "rootFile", "touchCount", "touchTime"},
    "AgLibraryFile": {"id_local", "baseName", "extension"},
    "Adobe_variablesTable": {"name", "value"},
}


class CatalogWriteError(RuntimeError):
    """The catalog cannot be written safely; nothing was changed."""


# --- Lightroom settings text -------------------------------------------------------------------------------------

def _brace_change(line: str) -> int:
    change, in_string, escaped = 0, False, False
    for ch in line:
        if in_string:
            if ch == '"' and not escaped:
                in_string = False
            escaped = ch == "\\" and not escaped
        elif ch == '"':
            in_string = True
        elif ch == "{":
            change += 1
        elif ch == "}":
            change -= 1
    return change


def parse_settings(text: str) -> tuple[list[tuple[str, str]], str]:
    """Split 's = { A = 1,\\nB = { ... },\\nC = 2 }' into top-level (key, 'key = value') entries + trailing newline."""
    body = text.rstrip("\n")
    trailer = text[len(body):]
    if not body.startswith("s = { ") or not body.endswith(" }"):
        raise ValueError("not a Lightroom settings table")
    entries, current, depth = [], [], 0
    for line in body[len("s = { "):-len(" }")].split("\n"):
        current.append(line)
        depth += _brace_change(line)
        if depth < 0:
            raise ValueError("unbalanced braces")
        if depth == 0:
            raw = "\n".join(current)
            raw = raw[:-1] if raw.endswith(",") else raw
            key = raw.split(" = ", 1)[0]
            if " = " not in raw or not key.replace("_", "").isalnum():
                raise ValueError(f"unreadable entry: {raw[:40]}")
            entries.append((key, raw))
            current = []
    if current:
        raise ValueError("unbalanced braces")
    return entries, trailer


def _lua(value: Any) -> str:
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return str(int(value)) if float(value).is_integer() else f"{value:.6g}"


def set_settings(text: str, values: Mapping[str, Any]) -> str:
    """Return the settings text with these keys set; new keys go where Lightroom puts them (byte-sorted order)."""
    entries, trailer = parse_settings(text)
    keys = [key for key, _ in entries]
    for key, value in values.items():
        raw = f"{key} = {_lua(value)}"
        if key in keys:
            entries[keys.index(key)] = (key, raw)
        else:
            pos = next((i for i, existing in enumerate(keys) if existing > key), len(keys))
            entries.insert(pos, (key, raw))
            keys.insert(pos, key)
    return "s = { " + ",\n".join(raw for _, raw in entries) + " }" + trailer


def read_settings(text: str) -> dict[str, str]:
    """Top-level key -> raw Lua value text."""
    return {key: raw.split(" = ", 1)[1] for key, raw in parse_settings(text)[0]}


def normalize_edit(values: Mapping[str, Any], *, is_raw: bool) -> dict[str, Any]:
    """Validate and round one photo's slider values; white balance becomes Lightroom's Custom white balance."""
    unknown = sorted(set(values) - set(WRITABLE))
    if unknown:
        raise ValueError(f"not a writable slider: {unknown}")
    out: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a number")
        low, high, decimals = WRITABLE[key]
        if not low <= value <= high:
            raise ValueError(f"{key}={value} outside {low}..{high}")
        if key in WHITE_BALANCE and not is_raw:
            continue  # JPEG/TIFF use a different white-balance scale; not learned yet
        out[key] = round(float(value), decimals) if decimals else int(round(value))
    if is_raw and any(key in out for key in WHITE_BALANCE):
        if not all(key in out for key in WHITE_BALANCE):
            raise ValueError("Temperature and Tint must be written together")
        out.update(WhiteBalance="Custom", CustomTemperature=out["Temperature"], CustomTint=out["Tint"])
    return out


# --- catalog access ----------------------------------------------------------------------------------------------

def catalog_in_use(catalog: Path) -> bool:
    """Lightroom keeps '<catalog>.lock' while open; a non-empty '-wal' means unsaved changes."""
    wal = Path(f"{catalog}-wal")
    return Path(f"{catalog}.lock").exists() or (wal.exists() and wal.stat().st_size > 0)


def _require_closed(catalog: Path) -> None:
    if not catalog.is_file():
        raise CatalogWriteError(f"catalog not found: {catalog}")
    if catalog_in_use(catalog):
        raise CatalogWriteError("Lightroom has this catalog open; close Lightroom and try again")


def backup_catalog(catalog: Path, backup_dir: Path | None = None) -> Path:
    """Consistent copy via SQLite's backup API. The '.lrcat-backup' suffix keeps Lightroom from opening it."""
    _require_closed(catalog)
    folder = backup_dir or catalog.parent / "ProGrapher Backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{catalog.stem}-{datetime.now():%Y%m%d-%H%M%S-%f}.lrcat-backup"
    src = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def restore_backup(backup: Path, catalog: Path) -> None:
    """Undo: put the catalog back exactly as it was when the backup was taken (Lightroom must be closed)."""
    _require_closed(catalog)
    if not backup.is_file():
        raise CatalogWriteError(f"backup not found: {backup}")
    src = sqlite3.connect(f"file:{backup}?mode=ro", uri=True)
    dst = sqlite3.connect(catalog)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _check_schema(db: sqlite3.Connection) -> None:
    for table, columns in REQUIRED.items():
        found = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
        if not columns <= found:
            raise CatalogWriteError(f"unsupported catalog layout: {table} lacks {sorted(columns - found)}")
    if db.execute("SELECT 1 FROM Adobe_variablesTable WHERE name = 'Adobe_entityIDCounter'").fetchone() is None:
        raise CatalogWriteError("unsupported catalog layout: no Adobe_entityIDCounter")


def _decode_history(blob: Any) -> tuple[str | None, str | None]:
    if isinstance(blob, str):
        return ("text", blob) if blob.lstrip().startswith("s = {") else (None, None)
    for method, decode in (("qcompress", lambda b: zlib.decompress(b[4:])), ("zlib", zlib.decompress)):
        try:
            text = decode(blob).decode("utf-8")
        except (zlib.error, UnicodeDecodeError):
            continue
        if text.lstrip().startswith("s = {"):
            return method, text
    return None, None


def _history_format(db: sqlite3.Connection) -> str:
    """History steps keep a full settings copy; Lightroom 15 stores it Qt-qCompress style (length + zlib)."""
    for (blob,) in db.execute("SELECT text FROM Adobe_libraryImageDevelopHistoryStep WHERE text IS NOT NULL "
                              "ORDER BY id_local DESC LIMIT 20"):
        method, _ = _decode_history(blob)
        if method:
            return method
    raise CatalogWriteError("unknown History-step format; nothing written")


def _encode_history(method: str, text: str) -> Any:
    raw = text.encode("utf-8")
    if method == "qcompress":
        return len(raw).to_bytes(4, "big") + zlib.compress(raw)
    return zlib.compress(raw) if method == "zlib" else text


def _process_version(column: Any, text: str) -> float | None:
    value = column or read_settings(text).get("ProcessVersion", "").strip('"')
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _edited_by_photographer(db: sqlite3.Connection, image: int, step_name: str) -> bool:
    names = [row[0] or "" for row in db.execute(
        "SELECT name FROM Adobe_libraryImageDevelopHistoryStep WHERE image = ?", (image,))]
    return any(not (name.startswith(AUTOMATIC_STEPS) or name == step_name) for name in names)


def write_edits(catalog: Path, edits: Mapping[int, Mapping[str, Any]], *, step_name: str = STEP_NAME,
                overwrite_photographer_edits: bool = False, backup_dir: Path | None = None) -> dict[str, Any]:
    """Write per-photo slider values ({Adobe_images.id_local: {"Exposure2012": 0.4, ...}}) into a closed catalog.

    Returns {"backup", "written", "skipped", "seconds"}; skipped photos carry a reason and are left unchanged.
    """
    catalog = Path(catalog)
    _require_closed(catalog)
    started = time.perf_counter()
    db = sqlite3.connect(catalog)
    try:
        _check_schema(db)
        method = _history_format(db)
        rows = {image: (settings_id, text or "", process, f"{base}.{ext}", (ext or "").lower() not in NON_RAW)
                for image, settings_id, text, process, base, ext in db.execute(
                    "SELECT i.id_local, s.id_local, s.text, s.processVersion, f.baseName, f.extension "
                    "FROM Adobe_images i JOIN Adobe_imageDevelopSettings s ON s.image = i.id_local "
                    "JOIN AgLibraryFile f ON f.id_local = i.rootFile")}
        planned, skipped = [], []
        for image, values in edits.items():  # validate everything before the first write
            if image not in rows:
                skipped.append({"image": image, "reason": "not_in_catalog"})
                continue
            settings_id, text, process, file_name, is_raw = rows[image]
            values = normalize_edit(values, is_raw=is_raw)
            version = _process_version(process, text) if text else None
            reason = ("no_values" if not values else
                      "unreadable_settings" if not text else
                      "old_or_unknown_process_version" if version is None or version < MIN_PROCESS_VERSION else
                      "edited_by_photographer" if not overwrite_photographer_edits
                      and _edited_by_photographer(db, image, step_name) else None)
            if reason is None:
                try:
                    planned.append((image, settings_id, file_name, set_settings(text, values), values))
                except ValueError:
                    reason = "unreadable_settings"
            if reason:
                skipped.append({"image": image, "file": file_name, "reason": reason})
    except BaseException:
        db.close()
        raise
    if not planned:
        db.close()
        return {"backup": None, "written": [], "skipped": skipped, "seconds": time.perf_counter() - started}
    backup = backup_catalog(catalog, backup_dir)
    try:
        now = time.time() - COCOA_EPOCH
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        written = []
        with db:
            counter = int(float(db.execute(
                "SELECT value FROM Adobe_variablesTable WHERE name = 'Adobe_entityIDCounter'").fetchone()[0]))
            has_change_counters = {"LrMobileSyncChangeCounter", "AgLibraryImageChangeCounter"} <= {
                row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            change = db.execute("SELECT changeCounter FROM LrMobileSyncChangeCounter").fetchone() \
                if has_change_counters else None
            change = int(change[0]) if change else None
            for image, settings_id, file_name, new_text, values in planned:
                digest, history_id = uuid.uuid4().hex, str(uuid.uuid4()).upper()
                db.execute("UPDATE Adobe_imageDevelopSettings SET text = ?, digest = ?, historySettingsID = ?, "
                           "hasDevelopAdjustmentsEx = 1, whiteBalance = COALESCE(?, whiteBalance) "
                           "WHERE id_local = ?",
                           (new_text, digest, history_id, values.get("WhiteBalance"), settings_id))
                counter += 1
                db.execute("INSERT INTO Adobe_libraryImageDevelopHistoryStep (id_local, id_global, dateCreated, "
                           "digest, hasBigData, hasDevelopAdjustments, image, name, relValueString, text, "
                           "valueString) VALUES (?, ?, ?, ?, 0, 1, ?, ?, NULL, ?, NULL)",
                           (counter, history_id, now, digest, image, step_name, _encode_history(method, new_text)))
                db.execute("UPDATE Adobe_images SET touchCount = COALESCE(touchCount, 0) + 1, touchTime = ? "
                           "WHERE id_local = ?", (now, image))
                if change is not None:
                    change += 1
                    db.execute("UPDATE AgLibraryImageChangeCounter SET changeCounter = ?, changedAtTime = ? "
                               "WHERE image = ?", (change, stamp, image))
                written.append({"image": image, "file": file_name})
            db.execute("UPDATE Adobe_variablesTable SET value = ? WHERE name = 'Adobe_entityIDCounter'", (counter,))
            if change is not None:
                db.execute("UPDATE LrMobileSyncChangeCounter SET changeCounter = ?", (change,))
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise CatalogWriteError("SQLite integrity check failed after writing")
    except BaseException:
        db.close()
        restore_backup(backup, catalog)
        raise
    db.close()
    return {"backup": str(backup), "written": written, "skipped": skipped, "seconds": time.perf_counter() - started}


__all__ = ["CatalogWriteError", "STEP_NAME", "WRITABLE", "backup_catalog", "catalog_in_use", "normalize_edit",
           "parse_settings", "read_settings", "restore_backup", "set_settings", "write_edits"]
