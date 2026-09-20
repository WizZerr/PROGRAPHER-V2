from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.platform.paths import user_data_dir


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PhotographerSetup:
    source_type: str | None
    catalog_path: str | None
    edits_folder_path: str | None
    style_name: str | None
    preset_path: str | None
    camera_profile: str | None
    color_profile_mode: str
    status: str
    updated_at: str | None


class PhotographerSetupStore:
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
        return connection

    def _ensure_column(
        self,
        db: sqlite3.Connection,
        column_name: str,
        definition: str,
    ) -> None:
        rows = db.execute("PRAGMA table_info(photographer_setup)").fetchall()
        columns = {row["name"] for row in rows}

        if column_name not in columns:
            db.execute(
                f"ALTER TABLE photographer_setup "
                f"ADD COLUMN {column_name} {definition}"
            )

    def _ensure_schema(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS photographer_setup (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    source_type TEXT,
                    catalog_path TEXT,
                    edits_folder_path TEXT,
                    style_name TEXT,
                    preset_path TEXT,
                    camera_profile TEXT,
                    color_profile_mode TEXT NOT NULL DEFAULT 'from_source',
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # Safe migrations from earlier Phase 7 builds.
            self._ensure_column(db, "source_type", "TEXT")
            self._ensure_column(db, "edits_folder_path", "TEXT")
            self._ensure_column(db, "preset_path", "TEXT")
            self._ensure_column(
                db,
                "color_profile_mode",
                "TEXT NOT NULL DEFAULT 'from_source'",
            )

    def get(self) -> PhotographerSetup:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT
                    source_type,
                    catalog_path,
                    edits_folder_path,
                    style_name,
                    preset_path,
                    camera_profile,
                    color_profile_mode,
                    status,
                    updated_at
                FROM photographer_setup
                WHERE singleton = 1
                """
            ).fetchone()

        if row is None:
            return PhotographerSetup(
                source_type=None,
                catalog_path=None,
                edits_folder_path=None,
                style_name=None,
                preset_path=None,
                camera_profile=None,
                color_profile_mode="from_source",
                status="no_profile",
                updated_at=None,
            )

        return PhotographerSetup(
            source_type=row["source_type"],
            catalog_path=row["catalog_path"],
            edits_folder_path=row["edits_folder_path"],
            style_name=row["style_name"],
            preset_path=row["preset_path"],
            camera_profile=row["camera_profile"],
            color_profile_mode=row["color_profile_mode"] or "from_source",
            status=row["status"],
            updated_at=row["updated_at"],
        )

    def _ensure_row(self, db: sqlite3.Connection) -> None:
        current = db.execute(
            "SELECT singleton FROM photographer_setup WHERE singleton = 1"
        ).fetchone()

        if current is None:
            db.execute(
                """
                INSERT INTO photographer_setup (
                    singleton,
                    source_type,
                    catalog_path,
                    edits_folder_path,
                    style_name,
                    preset_path,
                    camera_profile,
                    color_profile_mode,
                    status,
                    updated_at
                )
                VALUES (
                    1, NULL, NULL, NULL, NULL, NULL, NULL,
                    'from_source', 'no_profile', ?
                )
                """,
                (_utc_now(),),
            )

    def _upsert_source(
        self,
        *,
        source_type: str | None,
        catalog_path: str | None,
        edits_folder_path: str | None,
        status: str,
    ) -> PhotographerSetup:
        now = _utc_now()

        with self._connect() as db:
            self._ensure_row(db)
            db.execute(
                """
                UPDATE photographer_setup
                SET
                    source_type = ?,
                    catalog_path = ?,
                    edits_folder_path = ?,
                    status = ?,
                    updated_at = ?
                WHERE singleton = 1
                """,
                (
                    source_type,
                    catalog_path,
                    edits_folder_path,
                    status,
                    now,
                ),
            )

        return self.get()

    def save_catalog(self, catalog_path: str) -> PhotographerSetup:
        return self._upsert_source(
            source_type="lightroom_catalog",
            catalog_path=catalog_path,
            edits_folder_path=None,
            status="data_review",
        )

    def save_edits_folder(self, folder_path: str) -> PhotographerSetup:
        return self._upsert_source(
            source_type="edits_folder",
            catalog_path=None,
            edits_folder_path=folder_path,
            status="data_review",
        )

    def save_no_source(self) -> PhotographerSetup:
        return self._upsert_source(
            source_type="none",
            catalog_path=None,
            edits_folder_path=None,
            status="needs_more_data",
        )

    def save_style_preferences(
        self,
        *,
        style_name: str | None,
        preset_path: str | None,
        color_profile_mode: str,
        camera_profile: str | None,
    ) -> PhotographerSetup:
        now = _utc_now()

        with self._connect() as db:
            self._ensure_row(db)
            db.execute(
                """
                UPDATE photographer_setup
                SET
                    style_name = ?,
                    preset_path = ?,
                    color_profile_mode = ?,
                    camera_profile = ?,
                    updated_at = ?
                WHERE singleton = 1
                """,
                (
                    style_name,
                    preset_path,
                    color_profile_mode,
                    camera_profile,
                    now,
                ),
            )

        return self.get()
