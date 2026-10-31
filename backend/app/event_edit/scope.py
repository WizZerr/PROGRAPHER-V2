"""Event scope: the Lightroom folders that make up ONE event inside a catalog that may hold many.

Every step (anchors, dry run, completion, undo) works only on the photos of the chosen folders (and their
subfolders). A folder is identified by its root folder's id_global + its path inside the root, which stays the same
when the catalog is copied or moved; event_id is derived from the catalog file and those folder keys.
All reads here are read-only and never touch the catalog file (SQLite immutable mode).
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any


class ScopeError(ValueError):
    """The event scope is missing or does not match the catalog."""


def open_readonly(catalog: Path) -> sqlite3.Connection:
    """Read without changing a byte: immutable mode creates no -wal/-shm/journal file."""
    return sqlite3.connect(f"{Path(catalog).resolve().as_uri()}?mode=ro&immutable=1", uri=True)


def _folder_rows(db: sqlite3.Connection) -> list[tuple]:
    root_cols = {r[1] for r in db.execute("PRAGMA table_info(AgLibraryRootFolder)")}
    root_key = "r.id_global" if "id_global" in root_cols else "r.absolutePath"
    return db.execute(f"""SELECT fo.id_local, {root_key}, COALESCE(fo.pathFromRoot, ''), COALESCE(r.name, ''),
                                 COALESCE(r.absolutePath, '')
                          FROM AgLibraryFolder fo JOIN AgLibraryRootFolder r ON r.id_local = fo.rootFolder""").fetchall()


def folder_key(root_key: Any, path_from_root: str) -> str:
    return f"{root_key}|{path_from_root}"


def list_folders(catalog: Path) -> list[dict[str, Any]]:
    """Folders that hold photos, with counts and dates, for choosing the event (read-only)."""
    db = open_readonly(catalog)
    try:
        folders = {fid: (folder_key(rk, path), name, absolute, path) for fid, rk, path, name, absolute in _folder_rows(db)}
        stats: dict[int, list] = {}
        for fid, count, first, last in db.execute(
                """SELECT f.folder, COUNT(*), MIN(COALESCE(i.originalCaptureTime, i.captureTime)),
                          MAX(COALESCE(i.originalCaptureTime, i.captureTime))
                   FROM Adobe_images i JOIN AgLibraryFile f ON f.id_local = i.rootFile
                   WHERE i.masterImage IS NULL GROUP BY f.folder"""):
            stats[fid] = [count, first, last]
    except sqlite3.Error as exc:
        raise ScopeError("unsupported catalog layout") from exc
    finally:
        db.close()
    out = []
    for fid, (key, name, absolute, path) in folders.items():
        if fid in stats:
            count, first, last = stats[fid]
            out.append({"key": key, "label": f"{name}/{path}".rstrip("/"), "path": f"{absolute}{path}",
                        "photos": count, "first": (first or "")[:10], "last": (last or "")[:10]})
    return sorted(out, key=lambda f: (f["first"], f["label"]))


def scope_images(db: sqlite3.Connection, folder_keys: list[str]) -> set[int]:
    """Photos (virtual copies excluded) in the chosen folders and their subfolders. Unknown keys are an error."""
    if not folder_keys:
        raise ScopeError("no event folders chosen")
    rows = _folder_rows(db)
    known = {folder_key(rk, path) for _fid, rk, path, _n, _a in rows}
    unknown = [k for k in folder_keys if k not in known]
    if unknown:
        raise ScopeError(f"{len(unknown)} chosen folders are not in this catalog")
    chosen = [k.split("|", 1) for k in folder_keys]
    folder_ids = [fid for fid, rk, path, _n, _a in rows
                  if any(str(rk) == ck and path.startswith(cp) for ck, cp in chosen)]
    images: set[int] = set()
    for start in range(0, len(folder_ids), 500):
        chunk = folder_ids[start:start + 500]
        images |= {r[0] for r in db.execute(
            f"""SELECT i.id_local FROM Adobe_images i JOIN AgLibraryFile f ON f.id_local = i.rootFile
                WHERE i.masterImage IS NULL AND f.folder IN ({",".join("?" * len(chunk))})""", chunk)}
    return images


def event_id(catalog: Path, folder_keys: list[str]) -> str:
    raw = str(Path(catalog).resolve()).casefold() + "\n" + "\n".join(sorted(set(folder_keys)))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def fingerprint(db: sqlite3.Connection, images: set[int], collection: int | None = None) -> str:
    """Develop state of the event's photos (settings, History head, label) + ProGrapher's collection members.
    Any edit, label change, new History step or scope change since the dry run changes it."""
    h = hashlib.sha256()
    ordered = sorted(images)
    h.update(f"scope:{len(ordered)}:{','.join(map(str, ordered))}\n".encode())
    for start in range(0, len(ordered), 500):
        chunk = ordered[start:start + 500]
        marks = ",".join("?" * len(chunk))
        for row in db.execute(
                f"""SELECT i.id_local, COALESCE(s.text, ''), COALESCE(s.historySettingsID, ''),
                           COALESCE(i.colorLabels, ''),
                           (SELECT MAX(id_local) FROM Adobe_libraryImageDevelopHistoryStep WHERE image = i.id_local)
                    FROM Adobe_images i LEFT JOIN Adobe_imageDevelopSettings s ON s.image = i.id_local
                    WHERE i.id_local IN ({marks}) ORDER BY i.id_local""", chunk):
            h.update(repr(row).encode("utf-8"))
    if collection is not None:
        exists = db.execute("SELECT name FROM AgLibraryCollection WHERE id_local = ?", (collection,)).fetchone()
        members = [r[0] for r in db.execute(
            "SELECT image FROM AgLibraryCollectionImage WHERE collection = ? ORDER BY image", (collection,))]
        h.update(f"collection:{exists}:{members}".encode())
    return h.hexdigest()
