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


def _inspect_consistent_snapshot(catalog: Path, *, include_private: bool = False):
    """Audit a consistent copy; close handles and delete it on Windows."""
    private_dir = user_data_dir() / "learning_intake"
    private_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pg-lrcat-", dir=private_dir) as work:
        snapshot = Path(work) / "snapshot.lrcat"
        try:
            with closing(sqlite3.connect(catalog.as_uri() + "?mode=ro", uri=True, timeout=15)) as source:
                with closing(sqlite3.connect(snapshot)) as dest:
                    source.backup(dest, pages=2048, sleep=0.05)
            return inspect_catalog(snapshot, include_private=include_private)
        except (sqlite3.Error, CatalogIntakeError, OSError, ValueError) as exc:
            raise LearningIntakeError(
                "Catalog audit failed; no training performed. Use a closed, finalized Lightroom export if needed."
            ) from exc


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
            # Numbers only (counts, style medians, savings); no file names, paths of photos or images.
            db.execute("""
                CREATE TABLE IF NOT EXISTS learning_intake_analysis (
                    profile_id TEXT NOT NULL,
                    catalog_path TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL,
                    PRIMARY KEY (profile_id, catalog_path),
                    FOREIGN KEY (profile_id) REFERENCES learning_intake_profiles(profile_id)
                )
            """)

            # The editing style carried into new events (app/event_edit/style.py): numbers only.
            db.execute("""
                CREATE TABLE IF NOT EXISTS learning_intake_style (
                    profile_id TEXT PRIMARY KEY,
                    style_json TEXT NOT NULL,
                    learned_at TEXT NOT NULL,
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
            analyses = {r["catalog_path"]: r for r in db.execute(
                "SELECT * FROM learning_intake_analysis WHERE profile_id = ?", (profile_id,),
            )}
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
                "analysis": json.loads(analyses[entry["catalog_path"]]["summary_json"])
                if entry["catalog_path"] in analyses else None,
                "analyzed_at": analyses[entry["catalog_path"]]["analyzed_at"]
                if entry["catalog_path"] in analyses else None,
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
                "DELETE FROM learning_intake_analysis WHERE profile_id = ?",
                (profile_id,),
            )
            db.execute(
                "DELETE FROM learning_intake_style WHERE profile_id = ?",
                (profile_id,),
            )
            db.execute(
                "DELETE FROM learning_intake_catalogs WHERE profile_id = ?",
                (profile_id,),
            )
            db.execute(
                "DELETE FROM learning_intake_profiles WHERE profile_id = ?",
                (profile_id,),
            )

    def probe_smart_previews(self, profile_id: str, *, catalog_path: str) -> dict:
        """Read-only DNG content pilot on the Smart Previews path saved in profile."""
        from app.learning_intake.smart_preview_probe import inspect_smart_previews

        profile = self.get(profile_id)
        catalog = next(
            (entry for entry in profile["catalogs"] if entry["catalog_path"] == catalog_path),
            None,
        )
        if catalog is None:
            raise LearningIntakeError("Catalog is not linked to this profile.")
        stored = catalog.get("smart_previews_path")
        if not stored:
            return {
                "schema": "prographer.learning_intake.smart_preview_probe.v1",
                "status": "SMART_PREVIEWS_NOT_CONFIGURED",
                "source_kind": "smart_previews",
                "counts": {},
                "decode_attempts": 0,
                "decode_status_counts": {},
                "decoded_samples": [],
                "catalog_photo_identity_verified": False,
                "photo_to_dng_link_verified": False,
                "source_only_neutral_parity_verified": False,
                "photographer_finality_verified": False,
                "training_ready_samples": 0,
                "warnings": ["No Smart Previews folder is saved for this Lightroom catalog."],
            }
        try:
            source = _path(stored, directory=True)
        except (OSError, ValueError) as exc:
            raise LearningIntakeError(
                "Saved Smart Previews folder is missing. Re-audit the catalog location."
            ) from exc
        return inspect_smart_previews(source)

    def review_smart_preview_sdk_links(
        self, profile_id: str, *, catalog_path: str, evidence_path: str,
    ) -> dict:
        """Validate selected UUID→DNG paths from a manual read-only SDK pilot."""
        from app.learning_intake.sdk_link_review import verify_link_export

        profile = self.get(profile_id)
        entry = next(
            (item for item in profile["catalogs"] if item["catalog_path"] == catalog_path),
            None,
        )
        if entry is None:
            raise LearningIntakeError("Catalog is not linked to this profile.")
        if not entry.get("smart_previews_path"):
            raise LearningIntakeError("Profile has no Smart Preview directory.")
        try:
            catalog = _path(catalog_path, suffix=".lrcat")
            source = _path(entry["smart_previews_path"], directory=True)
            evidence = _path(evidence_path, suffix=".json")
        except (OSError, ValueError) as exc:
            raise LearningIntakeError("Catalog, Smart Previews or SDK evidence file unavailable.") from exc
        # Never permit writing research output inside the Lightroom package.
        if evidence.is_relative_to(source) or evidence == catalog:
            raise LearningIntakeError("SDK research evidence must be outside Lightroom folders.")
        _aggregate, private = _inspect_consistent_snapshot(catalog, include_private=True)
        if not private:
            raise LearningIntakeError("Private Lightroom catalog inventory unavailable.")
        return verify_link_export(
            evidence_path=evidence,
            catalog_path=catalog,
            preview_root=source,
            catalog_records=private["records"],
        )

    def link_smart_previews(self, profile_id: str, *, catalog_path: str, sample_size: int = 4) -> dict:
        """Stage 3: link catalog RAW photos to their Smart Preview DNGs (read only, nothing stored)."""
        from app.learning_intake.smart_preview_link import link_report

        source, records = self._smart_preview_sources(profile_id, catalog_path, sample_size)
        return link_report(source, records, sample_size=sample_size)

    def edit_pairs(self, profile_id: str, *, catalog_path: str, sample_size: int = 4) -> dict:
        """Stage 4: before (linked Smart Preview) / after (Develop values) pairs, in memory, never stored."""
        from app.learning_intake.edit_pairs import pairs_report

        source, records = self._smart_preview_sources(profile_id, catalog_path, sample_size)
        return pairs_report(source, records, sample_size=sample_size)

    def anchor_backtest(self, profile_id: str, *, catalog_path: str, anchors: int = 100,
                        sample_size: int = 4) -> dict:
        """Stage 5: replay the research anchor method on this catalog's pairs (measurement only, nothing stored)."""
        from app.learning_intake.anchor_backtest import backtest_report

        if not 5 <= anchors <= 500:
            raise LearningIntakeError("Anchors must be between 5 and 500.")
        source, records = self._smart_preview_sources(profile_id, catalog_path, sample_size)
        return backtest_report(source, records, anchors=anchors, sample_size=sample_size)

    def analyze_catalog(self, profile_id: str, *, catalog_path: str) -> dict:
        """Photographer flow: link, read edits, describe the style and measure savings in one pass.
        Stores the numeric summary with the profile; sample images are returned once and never stored."""
        from app.learning_intake.catalog_analysis import analyze

        source, records = self._smart_preview_sources(profile_id, catalog_path, 0)
        result = analyze(source, records)
        with self._db() as db:
            db.execute("""
                INSERT INTO learning_intake_analysis (profile_id, catalog_path, summary_json, analyzed_at)
                VALUES (?,?,?,?)
                ON CONFLICT(profile_id, catalog_path) DO UPDATE SET
                    summary_json=excluded.summary_json, analyzed_at=excluded.analyzed_at
            """, (profile_id, catalog_path, json.dumps(result["summary"], ensure_ascii=False, sort_keys=True), _now()))
        return {**result, "profile": self.get(profile_id)}

    def get_style(self, profile_id: str) -> dict | None:
        self.get(profile_id)
        with self._db() as db:
            row = db.execute("SELECT style_json, learned_at FROM learning_intake_style WHERE profile_id = ?",
                             (profile_id,)).fetchone()
        return {**json.loads(row["style_json"]), "learned_at": row["learned_at"]} if row else None

    def save_style(self, profile_id: str, style: dict) -> dict:
        self.get(profile_id)
        with self._db() as db:
            db.execute("""
                INSERT INTO learning_intake_style (profile_id, style_json, learned_at) VALUES (?,?,?)
                ON CONFLICT(profile_id) DO UPDATE SET style_json=excluded.style_json, learned_at=excluded.learned_at
            """, (profile_id, json.dumps(style, sort_keys=True), _now()))
        return self.get_style(profile_id)

    def learn_style(self, profile_id: str, progress=None) -> dict:
        """Learn the event-editing style from every catalog of the profile that has Smart Previews, and store it."""
        from app.event_edit import exposure_target as et, style as event_style
        from app.learning_intake.edit_pairs import build_pairs
        from app.learning_intake.smart_preview_link import build_links
        from app.learning_intake.smart_preview_probe import _count_dng_files

        pairs: list[dict] = []
        for entry in self.get(profile_id)["catalogs"]:
            if not entry.get("smart_previews_path"):
                continue
            try:
                source, records = self._smart_preview_sources(profile_id, entry["catalog_path"], 0)
            except LearningIntakeError:
                continue
            _counts, dngs = _count_dng_files(source)
            pairs += build_pairs(build_links(dngs, records)["links"])["pairs"]
        if not pairs:
            raise LearningIntakeError("No edited photos with Smart Previews in this profile to learn from.")
        measure, curve, _reason = et.face_measurer()
        return self.save_style(profile_id, event_style.learn(pairs, measure, curve, progress))

    def _smart_preview_sources(self, profile_id: str, catalog_path: str, sample_size: int):
        """Smart Previews folder + private catalog RAW records for a catalog linked to this profile."""
        if not 0 <= sample_size <= 4:
            raise LearningIntakeError("Sample size must be between 0 and 4.")
        profile = self.get(profile_id)
        entry = next(
            (item for item in profile["catalogs"] if item["catalog_path"] == catalog_path),
            None,
        )
        if entry is None:
            raise LearningIntakeError("Catalog is not linked to this profile.")
        if not entry.get("smart_previews_path"):
            raise LearningIntakeError("Profile has no Smart Preview directory.")
        try:
            catalog = _path(catalog_path, suffix=".lrcat")
            source = _path(entry["smart_previews_path"], directory=True)
        except (OSError, ValueError) as exc:
            raise LearningIntakeError("Catalog or Smart Previews folder unavailable.") from exc
        _aggregate, private = _inspect_consistent_snapshot(catalog, include_private=True)
        if not private:
            raise LearningIntakeError("Private Lightroom catalog inventory unavailable.")
        return source, private["records"]

    def preview_sample(
        self, profile_id: str, *, catalog_path: str,
        raw_folder: str | None = None, sample_size: int = 16,
    ) -> dict:
        """Review up to 16 local candidate rows; never persist filenames or IDs.

        Fail closed if the catalog is not already linked to this profile.
        Filename-only RAW candidates are NOT Lightroom identity matches.
        """
        from app.learning_intake.preflight import sample_preflight, MAX_SAMPLE

        if not 1 <= sample_size <= MAX_SAMPLE:
            raise LearningIntakeError("Sample size must be between 1 and 16.")
        profile = self.get(profile_id)
        if not any(item["catalog_path"] == catalog_path for item in profile["catalogs"]):
            raise LearningIntakeError("Catalog is not linked to this learning profile.")
        try:
            catalog = _path(catalog_path, suffix=".lrcat")
            root = _path(raw_folder, directory=True) if raw_folder else None
        except (OSError, ValueError) as exc:
            raise LearningIntakeError("Catalog or RAW folder is no longer accessible.") from exc

        probe = probe_catalog(catalog)
        if not probe.sqlite_valid or not probe.readable:
            raise LearningIntakeError("Catalog cannot be read safely: " + probe.note)

        _aggregate, private = _inspect_consistent_snapshot(catalog, include_private=True)
        if private is None:
            raise LearningIntakeError("Private research inventory unavailable.")
        result = sample_preflight(private, raw_root=root, sample_size=sample_size)
        # Per-photo evidence is transient; no manifests are written or uploaded.
        result["catalog_path"] = str(catalog)
        return result

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

        aggregate, private = _inspect_consistent_snapshot(catalog, include_private=False)
        assert private is None

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
