"""LB-02: write Develop edits straight into a Lightroom Classic catalog while Lightroom is closed (as Imagen does).

Evidence (docs/LB_02_DIRECT_CATALOG_WRITE.md): on a test catalog (Lightroom Classic, schema 1504001, settings
Version 18.7, Windows, 25 RAWs from 5 makers) Lightroom showed every written slider and Custom white balance,
recomputed the real digest after we stored a new one, refreshed the thumbnails, kept crops, and listed a
"ProGrapher" History step. Writing only the settings text (old digest) left stale thumbnails, so a new digest,
historySettingsID and History step are always written together.

Safety (every write goes through _write_session):
- one ProGrapher writer per catalog: an OS-level exclusive lock file (released by the OS if the process dies) plus an
  in-process lock, so two ProGrapher writes on one catalog cannot overlap;
- refuses while Lightroom has the catalog open (.lock file or unsaved -wal), checks again right before COMMIT;
- backup before writing (kept, never deleted by ProGrapher);
- one SQLite EXCLUSIVE transaction (busy timeout 0: if anything else holds the database the write stops at once);
  an optional `check` re-validates the catalog inside the transaction (e.g. "unchanged since the dry run");
- validation of every value before the first change; an optional allow-list refuses any photo outside the event;
- never changes keys other than the global sliders; leaves photos the photographer edited alone unless asked;
- integrity check after COMMIT, restoring the backup if SQLite reports damage.
Lightroom's own behaviour while ProGrapher holds the lock is not documented by Adobe: ProGrapher only promises to
stop, not that Lightroom cannot interfere.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
import uuid
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from app.platform.paths import user_data_dir

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


def lightroom_lock_present(catalog: Path) -> bool:
    """Only Lightroom creates '<catalog>.lock'. Used while ProGrapher writes: its own transaction fills the -wal file
    of a WAL catalog before COMMIT, so the -wal size says nothing about Lightroom at that point."""
    return Path(f"{catalog}.lock").exists()


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


# Catalog schema versions whose History-step format was verified in Lightroom (experiments 1-2, LB-02).
VERIFIED_HISTORY_FORMAT = {"1504001": "qcompress"}


def _history_format(db: sqlite3.Connection) -> str:
    """History steps keep a full settings copy; Lightroom 15 stores it Qt-qCompress style (length + zlib).
    Learnt from the catalog's own steps; a catalog with no step at all (e.g. after Clear History) uses the format
    verified for its schema version, and any other catalog is refused."""
    found_any = False
    for (blob,) in db.execute("SELECT text FROM Adobe_libraryImageDevelopHistoryStep WHERE text IS NOT NULL "
                              "ORDER BY id_local DESC LIMIT 20"):
        found_any = True
        method, _ = _decode_history(blob)
        if method:
            return method
    if not found_any:
        row = db.execute("SELECT value FROM Adobe_variablesTable WHERE name = 'Adobe_DBVersion'").fetchone()
        version = str(row[0]).split(".")[0] if row and row[0] is not None else ""
        if version in VERIFIED_HISTORY_FORMAT:
            return VERIFIED_HISTORY_FORMAT[version]
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


def develop_state(db: sqlite3.Connection, images) -> dict[int, dict[str, Any]]:
    """What undo needs to put a photo back: its Develop row and the id of its latest History step."""
    images = list(images)
    out: dict[int, dict[str, Any]] = {}
    for start in range(0, len(images), 500):
        chunk = images[start:start + 500]
        marks = ",".join("?" * len(chunk))
        for image, settings_id, text, digest, hist, wb, adj in db.execute(
                f"SELECT image, id_local, text, digest, historySettingsID, whiteBalance, hasDevelopAdjustmentsEx "
                f"FROM Adobe_imageDevelopSettings WHERE image IN ({marks})", chunk):
            out[image] = {"settings_id": settings_id, "text": text or "", "digest": digest, "historySettingsID": hist,
                          "whiteBalance": wb, "hasDevelopAdjustmentsEx": adj}
        for image, last in db.execute(
                f"SELECT image, id_global FROM Adobe_libraryImageDevelopHistoryStep h WHERE image IN ({marks}) "
                f"AND id_local = (SELECT MAX(id_local) FROM Adobe_libraryImageDevelopHistoryStep "
                f"WHERE image = h.image)", chunk):
            if image in out:
                out[image]["last_step"] = last
    return out


# --- exclusive write session -------------------------------------------------------------------------------------

_process_locks: dict[str, threading.Lock] = {}
_process_locks_guard = threading.Lock()


def _catalog_key(catalog: Path) -> str:
    return hashlib.sha256(str(Path(catalog).resolve()).casefold().encode("utf-8")).hexdigest()[:32]


@contextmanager
def catalog_lock(catalog: Path) -> Iterator[None]:
    """Exclusive ProGrapher lock for one catalog: fails at once (never waits) if another write holds it."""
    key = _catalog_key(catalog)
    with _process_locks_guard:
        local = _process_locks.setdefault(key, threading.Lock())
    if not local.acquire(blocking=False):
        raise CatalogWriteError("another ProGrapher operation is already writing this catalog")
    folder = user_data_dir() / "locks"
    folder.mkdir(parents=True, exist_ok=True)
    fd = os.open(folder / f"{key}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise CatalogWriteError("another ProGrapher operation is already writing this catalog") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
        local.release()


@contextmanager
def _write_session(catalog: Path, backup_dir: Path | None,
                   check: Callable[[sqlite3.Connection], None] | None) -> Iterator[tuple[sqlite3.Connection, Path]]:
    with catalog_lock(catalog):
        _require_closed(catalog)
        if check is not None:  # read-only pre-check: a plan that is already outdated never costs a backup
            ro = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
            try:
                check(ro)
            finally:
                ro.close()
        # The backup is taken before BEGIN (SQLite cannot back up from inside the exclusive transaction); `check`
        # runs again inside the transaction, so the write still only happens on the state the plan was made on.
        backup = backup_catalog(catalog, backup_dir)
        db = sqlite3.connect(catalog, isolation_level=None, timeout=0)
        committed = False
        try:
            db.execute("PRAGMA busy_timeout = 0")
            try:
                db.execute("BEGIN EXCLUSIVE")
            except sqlite3.OperationalError as exc:
                raise CatalogWriteError("the catalog is in use by another program; nothing was written") from exc
            if check is not None:
                check(db)
            yield db, backup
            if lightroom_lock_present(catalog):
                raise CatalogWriteError("Lightroom opened the catalog during the write; nothing was written")
            db.execute("COMMIT")
            committed = True
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise CatalogWriteError("SQLite integrity check failed after writing; the backup was restored")
        except BaseException:
            if not committed and db.in_transaction:
                db.execute("ROLLBACK")  # nothing of this write reaches the catalog
            db.close()
            if committed:
                restore_backup(backup, catalog)
            raise
        db.close()


def _next_ids(db: sqlite3.Connection, count: int) -> list[int]:
    counter = int(float(db.execute(
        "SELECT value FROM Adobe_variablesTable WHERE name = 'Adobe_entityIDCounter'").fetchone()[0]))
    db.execute("UPDATE Adobe_variablesTable SET value = ? WHERE name = 'Adobe_entityIDCounter'", (counter + count,))
    return list(range(counter + 1, counter + count + 1))


def _bump_change_counters(db: sqlite3.Connection, images: list[int], stamp: str) -> None:
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if not {"LrMobileSyncChangeCounter", "AgLibraryImageChangeCounter"} <= tables:
        return
    row = db.execute("SELECT changeCounter FROM LrMobileSyncChangeCounter").fetchone()
    if not row:
        return
    change = int(row[0])
    for image in images:
        change += 1
        db.execute("UPDATE AgLibraryImageChangeCounter SET changeCounter = ?, changedAtTime = ? WHERE image = ?",
                   (change, stamp, image))
    db.execute("UPDATE LrMobileSyncChangeCounter SET changeCounter = ?", (change,))


def _stamp() -> tuple[float, str]:
    return time.time() - COCOA_EPOCH, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# --- writing Develop settings ------------------------------------------------------------------------------------

def write_edits(catalog: Path, edits: Mapping[int, Mapping[str, Any]], *, step_name: str = STEP_NAME,
                overwrite_photographer_edits: bool = False, backup_dir: Path | None = None,
                allowed_images: set[int] | None = None, history_ids: Mapping[int, str] | None = None,
                check: Callable[[sqlite3.Connection], None] | None = None) -> dict[str, Any]:
    """Write per-photo slider values ({Adobe_images.id_local: {"Exposure2012": 0.4, ...}}) into a closed catalog.

    allowed_images: every photo must be in it, or nothing is written (event isolation).
    history_ids: the History step id to use per photo (lets a job prove afterwards what was written).
    check: called inside the write transaction before any change; raise to stop (e.g. catalog changed since plan).
    Returns {"backup", "written": [{image, file, history_id, before, values}], "skipped", "seconds"}; skipped photos
    carry a reason and are left unchanged; "before" is what undo needs.
    """
    catalog = Path(catalog)
    if allowed_images is not None:
        outside = sorted(set(edits) - set(allowed_images))
        if outside:
            raise CatalogWriteError(f"{len(outside)} photos are outside the event; nothing was written")
    _require_closed(catalog)
    started = time.perf_counter()
    db = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
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
    finally:
        db.close()
    if not planned:
        return {"backup": None, "written": [], "skipped": skipped, "seconds": time.perf_counter() - started}
    written = []
    with _write_session(catalog, backup_dir, check) as (db, backup):
        before = develop_state(db, [p[0] for p in planned])
        now, stamp = _stamp()
        step_ids = _next_ids(db, len(planned))
        for (image, settings_id, file_name, new_text, values), step_id in zip(planned, step_ids):
            digest = uuid.uuid4().hex
            history_id = (history_ids or {}).get(image) or str(uuid.uuid4()).upper()
            db.execute("UPDATE Adobe_imageDevelopSettings SET text = ?, digest = ?, historySettingsID = ?, "
                       "hasDevelopAdjustmentsEx = 1, whiteBalance = COALESCE(?, whiteBalance) WHERE id_local = ?",
                       (new_text, digest, history_id, values.get("WhiteBalance"), settings_id))
            db.execute("INSERT INTO Adobe_libraryImageDevelopHistoryStep (id_local, id_global, dateCreated, "
                       "digest, hasBigData, hasDevelopAdjustments, image, name, relValueString, text, "
                       "valueString) VALUES (?, ?, ?, ?, 0, 1, ?, ?, NULL, ?, NULL)",
                       (step_id, history_id, now, digest, image, step_name, _encode_history(method, new_text)))
            db.execute("UPDATE Adobe_images SET touchCount = COALESCE(touchCount, 0) + 1, touchTime = ? "
                       "WHERE id_local = ?", (now, image))
            written.append({"image": image, "file": file_name, "history_id": history_id,
                            "before": before.get(image), "values": {k: _lua(v) for k, v in values.items()}})
        _bump_change_counters(db, [w["image"] for w in written], stamp)
    return {"backup": str(backup), "written": written, "skipped": skipped, "seconds": time.perf_counter() - started}


def revert_edits(catalog: Path, entries: list[Mapping[str, Any]], *, backup_dir: Path | None = None,
                 check: Callable[[sqlite3.Connection], None] | None = None) -> dict[str, Any]:
    """Selective undo of a write_edits result: a photo is put back only if it is exactly as ProGrapher left it
    (its latest History step and historySettingsID are ProGrapher's, and every value written is still there).
    Anything changed since (an edit in Lightroom, another tool) is kept and reported, never overwritten."""
    catalog = Path(catalog)
    reverted, kept = [], []
    with _write_session(catalog, backup_dir, check) as (db, backup):
        state = develop_state(db, [e["image"] for e in entries])
        for entry in entries:
            image, now = entry["image"], state.get(entry["image"])
            before = entry.get("before") or {}
            reason = None
            if now is None or not before:
                reason = "missing"
            elif now["historySettingsID"] != entry["history_id"] or now.get("last_step") != entry["history_id"]:
                reason = "changed_after_prographer"
            else:
                try:
                    current = read_settings(now["text"])
                except ValueError:
                    current = {}
                if any(current.get(k) != v for k, v in entry["values"].items()):
                    reason = "changed_after_prographer"
            if reason:
                kept.append({"image": image, "reason": reason})
                continue
            db.execute("UPDATE Adobe_imageDevelopSettings SET text = ?, digest = ?, historySettingsID = ?, "
                       "whiteBalance = ?, hasDevelopAdjustmentsEx = ? WHERE image = ?",
                       (before["text"], before["digest"], before["historySettingsID"], before["whiteBalance"],
                        before["hasDevelopAdjustmentsEx"], image))
            db.execute("DELETE FROM Adobe_libraryImageDevelopHistoryStep WHERE image = ? AND id_global = ?",
                       (image, entry["history_id"]))
            reverted.append(image)
        _bump_change_counters(db, reverted, _stamp()[1])
    return {"backup": str(backup), "reverted": reverted, "kept": kept}


ANCHOR_COLLECTION = "ProGrapher - Edit these"
ANCHOR_LABEL = "Purple"
MARK_REQUIRED = {
    "AgLibraryCollection": {"id_local", "creationId", "genealogy", "name", "parent", "systemOnly"},
    "AgLibraryCollectionImage": {"id_local", "collection", "image", "pick"},
    "Adobe_images": {"id_local", "colorLabels"},
}


def collection_members(db: sqlite3.Connection, collection: int) -> list[int]:
    return [r[0] for r in db.execute("SELECT image FROM AgLibraryCollectionImage WHERE collection = ? ORDER BY "
                                     "id_local", (collection,))]


def mark_photos(catalog: Path, images: list[int], *, collection_name: str = ANCHOR_COLLECTION,
                owned_collection: int | None = None, expected_members: list[int] | None = None,
                label: str = ANCHOR_LABEL, backup_dir: Path | None = None, allowed_images: set[int] | None = None,
                check: Callable[[sqlite3.Connection], None] | None = None) -> dict[str, Any]:
    """Show the photographer which photos to edit: a top-level collection holding these photos, and a colour label
    on those without one (a label the photographer set is never changed). Verified in Lightroom Classic.

    A collection is reused only when ProGrapher owns it (`owned_collection`, recorded when ProGrapher created it)
    and it still holds exactly `expected_members`; otherwise a new collection is created and nothing existing is
    touched. A collection of the same name that ProGrapher did not create is never used: the new one gets a suffix.
    """
    catalog = Path(catalog)
    if allowed_images is not None and set(images) - set(allowed_images):
        raise CatalogWriteError("some photos are outside the event; nothing was written")
    _require_closed(catalog)
    db = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
    try:
        for table, cols in MARK_REQUIRED.items():
            found = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
            if not cols <= found:
                raise CatalogWriteError(f"unsupported catalog layout: {table} lacks {sorted(cols - found)}")
        known = {row[0] for row in db.execute("SELECT id_local FROM Adobe_images")}
    finally:
        db.close()
    wanted = list(dict.fromkeys(i for i in images if i in known))
    missing = [i for i in images if i not in known]
    if not wanted:
        return {"backup": None, "collection": None, "collection_name": None, "created": False, "marked": [],
                "labelled": [], "not_in_catalog": missing}
    with _write_session(catalog, backup_dir, check) as (db, backup):
        reuse = None
        if owned_collection is not None:
            row = db.execute("SELECT name FROM AgLibraryCollection WHERE id_local = ? AND parent IS NULL AND "
                             "creationId = 'com.adobe.ag.library.collection'", (owned_collection,)).fetchone()
            if row and row[0] == collection_name and collection_members(db, owned_collection) == list(expected_members or []):
                reuse = owned_collection
        if reuse is not None:
            collection, created = reuse, False
            db.execute("DELETE FROM AgLibraryCollectionImage WHERE collection = ?", (collection,))
        else:
            taken = {r[0] for r in db.execute("SELECT name FROM AgLibraryCollection")}
            name, n = collection_name, 2
            while name in taken:
                name, n = f"{collection_name} ({n})", n + 1
            collection_name, created = name, True
            collection = _next_ids(db, 1)[0]
            db.execute("INSERT INTO AgLibraryCollection (id_local, creationId, genealogy, name, parent, systemOnly) "
                       "VALUES (?, 'com.adobe.ag.library.collection', ?, ?, NULL, 0)",
                       (collection, f"/{len(str(collection))}{collection}", collection_name))
        for image, member_id in zip(wanted, _next_ids(db, len(wanted))):
            db.execute("INSERT INTO AgLibraryCollectionImage (id_local, collection, image, pick) VALUES (?, ?, ?, 0)",
                       (member_id, collection, image))
        labelled = [image for image in wanted if not (db.execute(
            "SELECT colorLabels FROM Adobe_images WHERE id_local = ?", (image,)).fetchone()[0] or "")]
        db.executemany("UPDATE Adobe_images SET colorLabels = ? WHERE id_local = ?",
                       [(label, image) for image in labelled])
    return {"backup": str(backup), "collection": collection, "collection_name": collection_name,
            "created": created, "marked": wanted, "labelled": labelled, "not_in_catalog": missing}


def unmark_photos(catalog: Path, collection: int, *, collection_name: str, expected_members: list[int],
                  labelled: list[int], label: str = ANCHOR_LABEL, backup_dir: Path | None = None,
                  check: Callable[[sqlite3.Connection], None] | None = None) -> dict[str, Any]:
    """Undo mark_photos: remove ProGrapher's collection only while it still has the name and exactly the photos
    ProGrapher put in it; clear only the labels ProGrapher set that still carry ProGrapher's label."""
    catalog = Path(catalog)
    with _write_session(catalog, backup_dir, check) as (db, backup):
        row = db.execute("SELECT name FROM AgLibraryCollection WHERE id_local = ?", (collection,)).fetchone()
        removed = bool(row and row[0] == collection_name
                       and sorted(collection_members(db, collection)) == sorted(expected_members))
        if removed:
            db.execute("DELETE FROM AgLibraryCollectionImage WHERE collection = ?", (collection,))
            db.execute("DELETE FROM AgLibraryCollection WHERE id_local = ?", (collection,))
        cleared = [i for i in labelled if (db.execute("SELECT colorLabels FROM Adobe_images WHERE id_local = ?",
                                                      (i,)).fetchone() or [""])[0] == label]
        db.executemany("UPDATE Adobe_images SET colorLabels = '' WHERE id_local = ?", [(i,) for i in cleared])
    return {"backup": str(backup), "collection_removed": removed, "labels_cleared": cleared,
            "labels_kept": sorted(set(labelled) - set(cleared))}


__all__ = ["ANCHOR_COLLECTION", "ANCHOR_LABEL", "CatalogWriteError", "STEP_NAME", "WRITABLE", "backup_catalog",
           "catalog_in_use", "catalog_lock", "lightroom_lock_present", "collection_members", "develop_state", "mark_photos", "normalize_edit",
           "parse_settings", "read_settings", "restore_backup", "revert_edits", "set_settings", "unmark_photos", "write_edits"]
