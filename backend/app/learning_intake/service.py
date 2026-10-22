"""PG-LI-00/01 — persistent profiles and safe catalog-only audit.

Catalogs are never modified. A consistent SQLite backup is created under
ProGrapher's private local data directory and removed after aggregate intake.
No original RAW bytes, private photo manifests or approved training pairs.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.photographer.lightroom import probe_catalog
from app.photographer.raw_catalog_intake import CatalogIntakeError, inspect_catalog
from app.platform.paths import user_data_dir


class LearningIntakeError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(value: str, *, suffix: str | None = None, directory: bool = False) -> Path:
    path = Path(value).expanduser()
    if path.is_symlink():
        raise LearningIntakeError("Symbolic links are not accepted for onboarding sources.")
    path = path.resolve(strict=True)
    if directory and not path.is_dir():
        raise LearningIntakeError("Expected a directory.")
    if not directory and not path.is_file():
        raise LearningIntakeError("Expected a file.")
    if suffix and path.suffix.casefold() != suffix:
        raise LearningIntakeError("Expected a " + suffix + " file.")
    return path


class LearningProfileStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (user_data_dir() / "prographer.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS learning_intake_profiles (
                    profile_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    photography_type TEXT NOT NULL,
                    color_mode TEXT NOT NULL,
                    consent INTEGER NOT NULL CHECK (consent = 1),
                    created_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS learning_intake_catalogs (
                    profile_id TEXT NOT NULL,
                    catalog_path TEXT NOT NULL,
                    smart_previews_path TEXT,
                    raw_fallback_path TEXT,
                    source_status TEXT NOT NULL,
                    aggregate_json TEXT NOT NULL,
                    audited_at TEXT NOT NULL,
                    PRIMARY KEY (profile_id, catalog_path),
                    FOREIGN KEY (profile_id) REFERENCES learning_intake_profiles(profile_id)
                )
            """)

    @contextmanager
    def _db(self):
        # The connection context manager commits but does not close its handle.
        # A real close is required on Windows and avoids accumulating handles.
        with closing(sqlite3.connect(self.db_path, timeout=30)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db

    def create(self, *, name: str, photography_type: str, color_mode: str, consent: bool) -> dict:
        name = name.strip()
        photography_type = photography_type.strip()
        if not name or len(name) > 120 or not photography_type or len(photography_type) > 80:
            raise LearningIntakeError("A profile name and photography type are required.")
        if color_mode not in {"color", "black_white"}:
            raise LearningIntakeError("Unsupported color mode.")
        if not consent:
            raise LearningIntakeError("Photographer permission is required before source intake.")
        profile_id = uuid.uuid4().hex
        with self._db() as db:
            db.execute(
                "INSERT INTO learning_intake_profiles VALUES (?,?,?,?,?,?)",
                (profile_id, name, photography_type, color_mode, 1, _now()),
            )
        return self.get(profile_id)

    def list(self) -> list[dict]:
        with self._db() as db:
            ids = [r["profile_id"] for r in db.execute(
                "SELECT profile_id FROM learning_intake_profiles ORDER BY created_at DESC, profile_id DESC"
            )]
        return [self.get(profile_id) for profile_id in ids]

    def get(self, profile_id: str) -> dict:
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM learning_intake_profiles WHERE profile_id = ?", (profile_id,)
            ).fetchone()
            if row is None:
                raise LearningIntakeError("Learning profile was not found.")
            catalogs = db.execute(
                "SELECT * FROM learning_intake_catalogs WHERE profile_id = ? ORDER BY audited_at, catalog_path",
                (profile_id,),
            ).fetchall()
        return {
            "profile_id": row["profile_id"],
            "name": row["name"],
            "photography_type": row["photography_type"],
            "color_mode": row["color_mode"],
            "created_at": row["created_at"],
            "status": "catalog_review" if catalogs else "waiting_for_catalog",
            "training_ready_samples": 0,
            "starting_point_verified": False,
            "catalogs": [{
                "catalog_path": entry["catalog_path"],
                "smart_previews_path": entry["smart_previews_path"],
                "raw_fallback_path": entry["raw_fallback_path"],
                "source_status": entry["source_status"],
                "aggregate": json.loads(entry["aggregate_json"]),
                "audited_at": entry["audited_at"],
            } for entry in catalogs],
        }

    def delete(self, profile_id: str) -> None:
        """Remove only this local onboarding profile and its stored metadata.

        Source .lrcat, RAW, Smart Previews and other profiles are untouched.
        Related rows are deleted first because existing SQLite installations
        intentionally do not use ON DELETE CASCADE on this table.
        """
        with self._db() as db:
            existing = db.execute(
                "SELECT 1 FROM learning_intake_profiles WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
            if existing is None:
                raise LearningIntakeError("Learning profile was not found.")
            db.execute(
                "DELETE FROM learning_intake_catalogs WHERE profile_id = ?",
                (profile_id,),
            )
            db.execute(
                "DELETE FROM learning_intake_profiles WHERE profile_id = ?",
                (profile_id,),
            )

    def attach_catalog(
        self, profile_id: str, *, catalog_path: str,
        smart_previews_path: str | None = None, raw_fallback_path: str | None = None,
    ) -> dict:
        self.get(profile_id)  # fail before expensive audit
        try:
            catalog = _path(catalog_path, suffix=".lrcat")
        except (OSError, ValueError) as exc:
            raise LearningIntakeError("Cannot access selected Lightroom catalog.") from exc

        smart = None
        raw = None
        if smart_previews_path:
            try:
                smart = _path(smart_previews_path, directory=True)
            except (OSError, ValueError) as exc:
                raise LearningIntakeError("Cannot access Smart Previews folder.") from exc
            if not smart.name.casefold().endswith("smart previews.lrdata"):
                raise LearningIntakeError("Choose a Lightroom Smart Previews.lrdata folder.")
        if smart is None:
            # Import here: discovery shares LearningIntakeError from this module.
            from app.learning_intake.discovery import find_smart_previews
            smart = find_smart_previews(catalog)
        if raw_fallback_path:
            try:
                raw = _path(raw_fallback_path, directory=True)
            except (OSError, ValueError) as exc:
                raise LearningIntakeError("Cannot access RAW fallback folder.") from exc
        if smart and raw and smart == raw:
            raise LearningIntakeError("Smart Previews and RAW fallback must be different folders.")

        probe = probe_catalog(catalog)
        if not probe.sqlite_valid or not probe.readable:
            raise LearningIntakeError("Lightroom catalog cannot be read safely: " + probe.note)

        # A new backup, not an immutable read of a potentially live catalog:
        # SQLite's online backup includes committed WAL records consistently.
        private_dir = user_data_dir() / "learning_intake"
        private_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pg-lrcat-", dir=private_dir) as work:
            snapshot = Path(work) / "snapshot.lrcat"
            try:
                # Both backup handles must close before TemporaryDirectory unlinks
                # snapshot.lrcat. A plain 'with sqlite3.connect' is insufficient.
                with closing(sqlite3.connect(catalog.as_uri() + "?mode=ro", uri=True, timeout=15)) as source:
                    with closing(sqlite3.connect(snapshot)) as destination:
                        source.backup(destination, pages=2048, sleep=0.05)
                aggregate, private = inspect_catalog(snapshot, include_private=False)
                assert private is None
            except (sqlite3.Error, CatalogIntakeError, OSError, ValueError) as exc:
                raise LearningIntakeError(
                    "Catalog audit failed; no training performed. Export a closed, finalized catalog copy if required."
                ) from exc

        # Deliberately keep only bounded, nonidentifying aggregates.
        totals = aggregate.get("totals", {})
        summary = {
            "schema": aggregate["schema"],
            "catalog_photo_records": totals.get("catalog_photo_records", 0),
            "catalog_raw_records": totals.get("catalog_raw_records", 0),
            "parsed_raw_records": totals.get("parsed_raw_records", 0),
            "candidate_folder_day_groups": aggregate.get("candidate_folder_day_groups", 0),
            "exclusions": aggregate.get("exclusions", {}),
            "training_ready_samples": 0,
            "warnings": [
                "Event identity, original image match and final photographer edit remain unverified.",
                "Reset versus Import and approved initial Develop state remain unverified.",
                "Catalog + source folder linkage is unverified; no personal Brain has been trained.",
            ],
        }
        source_status = (
            "smart_previews_unverified" if smart
            else "raw_fallback_unverified" if raw
            else "catalog_only_limited"
        )
        with self._db() as db:
            db.execute("""
                INSERT INTO learning_intake_catalogs
                    (profile_id, catalog_path, smart_previews_path, raw_fallback_path,
                     source_status, aggregate_json, audited_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(profile_id,catalog_path) DO UPDATE SET
                    smart_previews_path=excluded.smart_previews_path,
                    raw_fallback_path=excluded.raw_fallback_path,
                    source_status=excluded.source_status,
                    aggregate_json=excluded.aggregate_json,
                    audited_at=excluded.audited_at
            """, (
                profile_id, str(catalog), str(smart) if smart else None,
                str(raw) if raw else None, source_status,
                json.dumps(summary, ensure_ascii=False, sort_keys=True), _now(),
            ))
        return self.get(profile_id)
