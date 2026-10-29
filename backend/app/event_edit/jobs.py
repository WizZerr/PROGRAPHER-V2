"""Local job store for event operations (anchors, completion, undo): every catalog change is a job.

Lifecycle: pending -> planning -> planned (dry run done, nothing written)
           planned --confirm--> queued -> writing -> completed | failed | outdated
           planned/pending/planning --cancel--> cancelled          (never while writing)
           completed completion job --undo--> undone
A job left in pending/planning/queued/writing by a crash is recovered on the next read: planning jobs become
"interrupted" (nothing was written); writing jobs are checked against the catalog (writes are one transaction, so
either everything or nothing happened) and become completed or failed accordingly. Stored under the ProGrapher data
directory; never inside the catalog folder. Plans can hold per-photo values, so the store is private local data.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

from app.platform.paths import user_data_dir

ACTIVE = ("pending", "planning", "queued", "writing")
_running: set[str] = set()
_running_guard = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY, kind TEXT NOT NULL, event_id TEXT NOT NULL, catalog TEXT NOT NULL,
    scope_json TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
    plan_json TEXT, fingerprint TEXT, result_json TEXT, error TEXT, parent_job TEXT,
    progress_done INTEGER NOT NULL DEFAULT 0, progress_total INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY, catalog TEXT NOT NULL, scope_json TEXT NOT NULL, collection_id INTEGER,
    collection_name TEXT, anchors_json TEXT, labelled_json TEXT, updated REAL NOT NULL);
"""


def _db() -> sqlite3.Connection:
    folder = user_data_dir() / "event_edit"
    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(folder / "jobs.sqlite", timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def create(kind: str, event_id: str, catalog: Path, scope: list[str], parent_job: str | None = None) -> str:
    job_id = uuid.uuid4().hex
    now = time.time()
    with closing(_db()) as db, db:
        db.execute("INSERT INTO jobs (job_id, kind, event_id, catalog, scope_json, status, created, updated, "
                   "parent_job) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
                   (job_id, kind, event_id, str(catalog), json.dumps(scope), now, now, parent_job))
    return job_id


def update(job_id: str, **fields: Any) -> None:
    for key in ("plan", "result"):
        if key in fields:
            fields[f"{key}_json"] = json.dumps(fields.pop(key))
    fields["updated"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with closing(_db()) as db, db:
        db.execute(f"UPDATE jobs SET {cols} WHERE job_id = ?", (*fields.values(), job_id))


def finish_planning(job_id: str, **fields: Any) -> bool:
    """Store a finished dry run only if the job is still planning (a cancel meanwhile wins)."""
    for key in ("plan", "result"):
        if key in fields:
            fields[f"{key}_json"] = json.dumps(fields.pop(key))
    fields["updated"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with closing(_db()) as db, db:
        cur = db.execute(f"UPDATE jobs SET {cols} WHERE job_id = ? AND status = 'planning'", (*fields.values(), job_id))
        return cur.rowcount == 1


def transition(job_id: str, allowed: tuple[str, ...], new: str) -> bool:
    """Atomically move a job to `new` only from one of `allowed` (prevents double confirm/run)."""
    with closing(_db()) as db, db:
        marks = ",".join("?" * len(allowed))
        cur = db.execute(f"UPDATE jobs SET status = ?, updated = ? WHERE job_id = ? AND status IN ({marks})",
                         (new, time.time(), job_id, *allowed))
        return cur.rowcount == 1


def get(job_id: str) -> dict[str, Any] | None:
    with closing(_db()) as db:
        row = db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    job = dict(row)
    job["scope"] = json.loads(job.pop("scope_json"))
    job["plan"] = json.loads(job.pop("plan_json")) if job.get("plan_json") else None
    job["result"] = json.loads(job.pop("result_json")) if job.get("result_json") else None
    return job


def jobs_for_catalog(catalog: Path, statuses: tuple[str, ...]) -> list[dict[str, Any]]:
    with closing(_db()) as db:
        marks = ",".join("?" * len(statuses))
        rows = db.execute(f"SELECT job_id FROM jobs WHERE catalog = ? AND status IN ({marks})",
                          (str(catalog), *statuses)).fetchall()
    return [j for j in (get(r[0]) for r in rows) if j]


def jobs_for_event(event_id: str, kind: str) -> list[dict[str, Any]]:
    with closing(_db()) as db:
        rows = db.execute("SELECT job_id FROM jobs WHERE event_id = ? AND kind = ? ORDER BY created",
                          (event_id, kind)).fetchall()
    return [j for j in (get(r[0]) for r in rows) if j]


def get_event(event_id: str) -> dict[str, Any] | None:
    with closing(_db()) as db:
        row = db.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
    if row is None:
        return None
    event = dict(row)
    for key in ("scope_json", "anchors_json", "labelled_json"):
        event[key[:-5]] = json.loads(event.pop(key)) if event.get(key) else []
    return event


def save_event(event_id: str, catalog: Path, scope: list[str], **fields: Any) -> None:
    current = get_event(event_id) or {}
    values = {"collection_id": current.get("collection_id"), "collection_name": current.get("collection_name"),
              "anchors": current.get("anchors", []), "labelled": current.get("labelled", []), **fields}
    with closing(_db()) as db, db:
        db.execute("INSERT OR REPLACE INTO events (event_id, catalog, scope_json, collection_id, collection_name, "
                   "anchors_json, labelled_json, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (event_id, str(catalog), json.dumps(scope), values["collection_id"], values["collection_name"],
                    json.dumps(values["anchors"]), json.dumps(values["labelled"]), time.time()))


def is_running(job_id: str) -> bool:
    with _running_guard:
        return job_id in _running


def run(job_id: str, work: Callable[[], None], wait: bool) -> None:
    """Run `work` for a job in a background thread (or inline when wait=True); it updates the job itself."""
    with _running_guard:
        if job_id in _running:
            raise RuntimeError("job already running")
        _running.add(job_id)

    def target() -> None:
        try:
            work()
        finally:
            with _running_guard:
                _running.discard(job_id)
    if wait:
        target()
    else:
        threading.Thread(target=target, name=f"event-job-{job_id[:8]}", daemon=True).start()


def path(job: dict[str, Any]) -> Path:
    return Path(job["catalog"])
