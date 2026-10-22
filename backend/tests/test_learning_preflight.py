"""PG-LI-02A: local-only, fail-closed dataset sample tests (synthetic data)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from app.learning_intake.preflight import choose_sample, sample_preflight
from app.learning_intake.service import LearningIntakeError, LearningProfileStore


def make_fixture(path: Path, count: int = 20) -> None:
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE Adobe_images (
          id_local INTEGER PRIMARY KEY, id_global TEXT, rootFile INTEGER,
          fileFormat TEXT, captureTime TEXT, originalCaptureTime TEXT,
          masterImage INTEGER, copyName TEXT);
        CREATE TABLE AgLibraryFile (
          id_local INTEGER PRIMARY KEY, id_global TEXT, baseName TEXT,
          extension TEXT, folder INTEGER);
        CREATE TABLE AgLibraryFolder (
          id_local INTEGER PRIMARY KEY, rootFolder INTEGER, pathFromRoot TEXT);
        CREATE TABLE AgLibraryRootFolder (id_local INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE Adobe_imageDevelopSettings (
          id_local INTEGER PRIMARY KEY, image INTEGER, text TEXT,
          processVersion TEXT, whiteBalance TEXT, grayscale INTEGER);
        """)
        db.execute("INSERT INTO AgLibraryRootFolder VALUES (1, 'privateRoot')")
        db.executemany("INSERT INTO AgLibraryFolder VALUES (?,?,?)", [
            (2, 1, 'A'), (3, 1, 'B'),
        ])
        for i in range(1, count + 1):
            folder = 2 if i % 2 else 3
            db.execute(
                "INSERT INTO AgLibraryFile VALUES (?,?,?,?,?)",
                (i, f"file-{i}", f"photo_{i:04d}", "cr3", folder),
            )
            db.execute(
                "INSERT INTO Adobe_images VALUES (?,?,?,?,?,?,?,?)",
                (i, f"image-{i}", i, "RAW", "2026-09-01 12:00:00", None,
                 999 if i == 3 else None, "Alt" if i == 3 else None),
            )
            db.execute(
                "INSERT INTO Adobe_imageDevelopSettings VALUES (?,?,?,?,?,?)",
                (i, i, "s={ Exposure2012=0.5, Temperature=5200, Tint=10 }",
                 "15.4", "As Shot", 0),
            )


def test_pilot_distributes_safely_across_candidate_groups():
    rows = [
        {"catalog_image_id": i, "event_group_id": "G0001" if i < 10 else "G0002"}
        for i in range(20)
    ]
    picked = choose_sample(rows, sample_size=16)
    assert len(picked) == 16
    assert len({item["catalog_image_id"] for item in picked}) == 16
    assert {item["event_group_id"] for item in picked} == {"G0001", "G0002"}
    with pytest.raises(LearningIntakeError):
        choose_sample(rows, sample_size=17)


def test_preflight_catalog_and_raw_hash_never_promote_training(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "private"))
    catalog = tmp_path / "wedding.lrcat"
    make_fixture(catalog)
    original_hash = hashlib.sha256(catalog.read_bytes()).hexdigest()
    root = tmp_path / "Raw originals"
    root.mkdir()
    for i in range(1, 21):
        (root / f"photo_{i:04d}.CR3").write_bytes(f"RAW original {i}".encode())

    store = LearningProfileStore()
    profile = store.create(name="Wedding", photography_type="wedding",
                           color_mode="color", consent=True)
    store.attach_catalog(profile["profile_id"], catalog_path=str(catalog))

    report = store.preview_sample(
        profile["profile_id"], catalog_path=str(catalog), raw_folder=str(root),
    )
    assert report["sample_count"] == 16
    assert report["group_count_in_sample"] == 2
    assert report["training_ready_samples"] == 0
    assert report["source_identity_verified_count"] == 0
    assert report["finality_verified_count"] == 0
    assert all(row["training_eligible"] is False for row in report["records"])
    assert all(row["source_sha256"] and len(row["source_sha256"]) == 64 for row in report["records"])
    assert all(row["source_match_status"] == "unique_filename_candidate" for row in report["records"])
    assert any("virtual_copy_requires_selection" in row["issues"] for row in report["records"])
    assert hashlib.sha256(catalog.read_bytes()).hexdigest() == original_hash
    assert not list((tmp_path / "private" / "learning_intake").glob("pg-lrcat-*"))

    # Private per-photo records should never be written into persisted
    # aggregate summaries, even after the sample has been viewed.
    profile_json = json.dumps(store.get(profile["profile_id"]), ensure_ascii=False)
    assert "photo_0001" not in profile_json
    assert "SHA-256" not in profile_json
    assert "file_stem" not in profile_json


def test_ambiguous_sources_never_arbitrarily_choose_first(tmp_path: Path):
    root = tmp_path / "RAW"
    (root / "event_a").mkdir(parents=True)
    (root / "event_b").mkdir()
    (root / "event_a" / "same.CR3").write_bytes(b"one")
    (root / "event_b" / "same.CR3").write_bytes(b"two")
    private = {"records": [{
        "catalog_image_id": 1, "file_stem": "same", "extension": "cr3",
        "event_group_id": "G0001", "capture_day": "2026-09-01",
        "develop": {}, "parse_exclusion": None,
    }]}
    report = sample_preflight(private, raw_root=root)
    assert report["records"][0]["source_match_status"] == "ambiguous_filename"
    assert report["records"][0]["source_sha256"] is None
    assert report["records"][0]["source_candidate_path"] is None
    assert report["training_ready_samples"] == 0


def test_catalog_only_sample_stays_unverified(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "private"))
    catalog = tmp_path / "test.lrcat"
    make_fixture(catalog, count=2)
    store = LearningProfileStore()
    profile_id = store.create(name="A", photography_type="wedding",
                              color_mode="color", consent=True)["profile_id"]
    store.attach_catalog(profile_id, catalog_path=str(catalog))
    report = store.preview_sample(profile_id, catalog_path=str(catalog))
    assert report["sample_count"] == 2
    assert report["source_match_counts"] == {"raw_folder_not_selected": 2}
    assert all(not entry["training_eligible"] for entry in report["records"])


def test_unlinked_catalog_and_missing_profile_are_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "private"))
    catalog = tmp_path / "not-linked.lrcat"
    make_fixture(catalog)
    store = LearningProfileStore()
    profile_id = store.create(name="A", photography_type="wedding",
                              color_mode="color", consent=True)["profile_id"]
    with pytest.raises(LearningIntakeError, match="not linked"):
        store.preview_sample(profile_id, catalog_path=str(catalog))
    with pytest.raises(LearningIntakeError, match="not found"):
        store.preview_sample("unknown", catalog_path=str(catalog))


def test_missing_and_uncertain_develop_never_become_training_eligible():
    private = {"records": [{
        "catalog_image_id": 1, "file_stem": "bad", "extension": "cr3",
        "event_group_id": "G0001", "capture_day": "unknown",
        "develop": {}, "parse_exclusion": "missing_develop",
        "virtual_copy_candidate": True, "opaque_edit_review_required": True,
        "unsupported_fields": ["UnknownDevelopControl"],
    }]}
    report = sample_preflight(private)
    sample = report["records"][0]
    assert sample["develop_parse_ok"] is False
    assert "missing_develop" in sample["issues"]
    assert "virtual_copy_requires_selection" in sample["issues"]
    assert "unsupported_local_edit_review_required" in sample["issues"]
    assert "unmapped_develop_fields" in sample["issues"]
    assert sample["training_eligible"] is False
