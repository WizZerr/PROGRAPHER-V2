from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.ingest.scanner import ScannedSource
from app.platform.paths import user_data_dir


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root_key(path: Path) -> str:
    text = str(path.resolve())
    if os.name == "nt":
        text = text.casefold()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EventRecord:
    id: str
    name: str
    root_path: str
    total_files: int
    raw_files: int
    rendered_files: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class EventOpenResult:
    event: EventRecord
    duplicate_files_ignored: int
    new_files_added: int
    result: str  # created | existing | updated


@dataclass(frozen=True)
class EventAvailability:
    event_id: str
    root_exists: bool
    tracked_files: int
    available_files: int
    missing_files: int


@dataclass(frozen=True)
class RelinkResult:
    event: EventRecord
    matched_files: int
    missing_files: int
    new_files_added: int


class EventStore:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = (
            database_path
            if database_path is not None
            else user_data_dir() / "prographer.sqlite3"
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    root_key TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS event_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    absolute_path TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    modified_ns INTEGER NOT NULL,
                    present INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
                    UNIQUE(event_id, fingerprint)
                );

                CREATE INDEX IF NOT EXISTS idx_event_files_event
                ON event_files(event_id);

                CREATE INDEX IF NOT EXISTS idx_event_files_fingerprint
                ON event_files(fingerprint);
                """
            )

    def open_folder(
        self,
        root: Path,
        sources: list[ScannedSource],
        name: str | None = None,
    ) -> EventOpenResult:
        canonical_root = root.resolve()
        key = _root_key(canonical_root)
        event_id = key[:24]
        now = _utc_now()
        display_name = (name or canonical_root.name or "אירוע").strip()

        duplicate_files_ignored = 0
        new_files_added = 0
        seen_fingerprints: set[str] = set()

        with self._connect() as db:
            existing = db.execute(
                "SELECT id, created_at FROM events WHERE root_key = ?",
                (key,),
            ).fetchone()

            was_existing = existing is not None
            created_at = existing["created_at"] if existing else now

            existing_fingerprints: set[str] = set()
            if was_existing:
                rows = db.execute(
                    "SELECT fingerprint FROM event_files WHERE event_id = ?",
                    (event_id,),
                ).fetchall()
                existing_fingerprints = {row["fingerprint"] for row in rows}

            db.execute(
                """
                INSERT INTO events (
                    id, root_key, name, root_path, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(root_key) DO UPDATE SET
                    name = excluded.name,
                    root_path = excluded.root_path,
                    updated_at = excluded.updated_at
                """,
                (
                    event_id,
                    key,
                    display_name,
                    str(canonical_root),
                    created_at,
                    now,
                ),
            )

            db.execute(
                "UPDATE event_files SET present = 0 WHERE event_id = ?",
                (event_id,),
            )

            for source in sources:
                if source.fingerprint in seen_fingerprints:
                    duplicate_files_ignored += 1
                    continue

                seen_fingerprints.add(source.fingerprint)

                if source.fingerprint not in existing_fingerprints:
                    new_files_added += 1

                db.execute(
                    """
                    INSERT INTO event_files (
                        event_id,
                        fingerprint,
                        absolute_path,
                        relative_path,
                        filename,
                        extension,
                        source_type,
                        size_bytes,
                        modified_ns,
                        present
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(event_id, fingerprint) DO UPDATE SET
                        absolute_path = excluded.absolute_path,
                        relative_path = excluded.relative_path,
                        filename = excluded.filename,
                        extension = excluded.extension,
                        source_type = excluded.source_type,
                        size_bytes = excluded.size_bytes,
                        modified_ns = excluded.modified_ns,
                        present = 1
                    """,
                    (
                        event_id,
                        source.fingerprint,
                        source.absolute_path,
                        source.relative_path,
                        source.filename,
                        source.extension,
                        source.source_type,
                        source.size_bytes,
                        source.modified_ns,
                    ),
                )

            db.execute(
                "UPDATE events SET updated_at = ? WHERE id = ?",
                (now, event_id),
            )

        if not was_existing:
            result = "created"
        elif new_files_added > 0:
            result = "updated"
        else:
            result = "existing"

        return EventOpenResult(
            event=self.get_event(event_id),
            duplicate_files_ignored=duplicate_files_ignored,
            new_files_added=new_files_added,
            result=result,
        )

    def get_event(self, event_id: str) -> EventRecord:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT
                    e.id,
                    e.name,
                    e.root_path,
                    e.created_at,
                    e.updated_at,
                    COUNT(f.id) FILTER (WHERE f.present = 1) AS total_files,
                    COUNT(f.id) FILTER (
                        WHERE f.present = 1 AND f.source_type = 'raw'
                    ) AS raw_files,
                    COUNT(f.id) FILTER (
                        WHERE f.present = 1 AND f.source_type = 'rendered'
                    ) AS rendered_files
                FROM events e
                LEFT JOIN event_files f ON f.event_id = e.id
                WHERE e.id = ?
                GROUP BY e.id
                """,
                (event_id,),
            ).fetchone()

        if row is None:
            raise KeyError(event_id)

        return EventRecord(
            id=row["id"],
            name=row["name"],
            root_path=row["root_path"],
            total_files=int(row["total_files"] or 0),
            raw_files=int(row["raw_files"] or 0),
            rendered_files=int(row["rendered_files"] or 0),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_events(self) -> list[EventRecord]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id FROM events ORDER BY updated_at DESC"
            ).fetchall()

        return [self.get_event(row["id"]) for row in rows]

    def availability(self, event_id: str) -> EventAvailability:
        event = self.get_event(event_id)
        root = Path(event.root_path)
        root_exists = root.exists() and root.is_dir()

        with self._connect() as db:
            rows = db.execute(
                """
                SELECT absolute_path
                FROM event_files
                WHERE event_id = ? AND present = 1
                """,
                (event_id,),
            ).fetchall()

        tracked = len(rows)
        available = 0

        if root_exists:
            for row in rows:
                try:
                    if Path(row["absolute_path"]).is_file():
                        available += 1
                except OSError:
                    pass

        return EventAvailability(
            event_id=event_id,
            root_exists=root_exists,
            tracked_files=tracked,
            available_files=available,
            missing_files=max(0, tracked - available),
        )

    def relink_event(
        self,
        event_id: str,
        new_root: Path,
        sources: list[ScannedSource],
    ) -> RelinkResult:
        event = self.get_event(event_id)
        canonical_root = new_root.resolve()
        new_key = _root_key(canonical_root)
        now = _utc_now()

        with self._connect() as db:
            conflict = db.execute(
                "SELECT id FROM events WHERE root_key = ? AND id != ?",
                (new_key, event_id),
            ).fetchone()
            if conflict is not None:
                raise ValueError("התיקייה כבר משויכת לאירוע אחר.")

            rows = db.execute(
                """
                SELECT fingerprint
                FROM event_files
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchall()
            known_fingerprints = {row["fingerprint"] for row in rows}

            source_map = {source.fingerprint: source for source in sources}
            matched = known_fingerprints.intersection(source_map.keys())

            if known_fingerprints and not matched:
                raise ValueError(
                    "לא נמצאה התאמה לקבצי המקור של האירוע בתיקייה שנבחרה."
                )

            db.execute(
                """
                UPDATE events
                SET root_key = ?, root_path = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_key, str(canonical_root), now, event_id),
            )

            db.execute(
                "UPDATE event_files SET present = 0 WHERE event_id = ?",
                (event_id,),
            )

            new_files_added = 0

            for source in sources:
                if source.fingerprint not in known_fingerprints:
                    new_files_added += 1

                db.execute(
                    """
                    INSERT INTO event_files (
                        event_id,
                        fingerprint,
                        absolute_path,
                        relative_path,
                        filename,
                        extension,
                        source_type,
                        size_bytes,
                        modified_ns,
                        present
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(event_id, fingerprint) DO UPDATE SET
                        absolute_path = excluded.absolute_path,
                        relative_path = excluded.relative_path,
                        filename = excluded.filename,
                        extension = excluded.extension,
                        source_type = excluded.source_type,
                        size_bytes = excluded.size_bytes,
                        modified_ns = excluded.modified_ns,
                        present = 1
                    """,
                    (
                        event_id,
                        source.fingerprint,
                        source.absolute_path,
                        source.relative_path,
                        source.filename,
                        source.extension,
                        source.source_type,
                        source.size_bytes,
                        source.modified_ns,
                    ),
                )

        refreshed = self.get_event(event_id)
        availability = self.availability(event_id)

        return RelinkResult(
            event=refreshed,
            matched_files=len(matched),
            missing_files=availability.missing_files,
            new_files_added=new_files_added,
        )
