"""PG-LI-00/01: non-destructive catalog-first intake regression tests."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from app.learning_intake.service import LearningIntakeError, LearningProfileStore


def make_catalog(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE Adobe_images (
                id_local INTEGER PRIMARY KEY, id_global TEXT, rootFile INTEGER,
                fileFormat TEXT, captureTime TEXT, originalCaptureTime TEXT,
                masterImage INTEGER, copyName TEXT
            );
            CREATE TABLE AgLibraryFile (
                id_local INTEGER PRIMARY KEY, id_global TEXT, baseName TEXT,
                extension TEXT, folder INTEGER
            );
            CREATE TABLE AgLibraryFolder (
                id_local INTEGER PRIMARY KEY, rootFolder INTEGER, pathFromRoot TEXT
            );
            CREATE TABLE AgLibraryRootFolder (id_local INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE Adobe_imageDevelopSettings (
                id_local INTEGER PRIMARY KEY, image INTEGER, text TEXT,
                processVersion TEXT, whiteBalance TEXT, grayscale INTEGER
            );
        """)
        db.execute(
            "INSERT INTO Adobe_images VALUES (1, 'img-1', 7, 'RAW', '2026-09-20 11:40:00', NULL, NULL, NULL)"
        )
        db.execute(
            "INSERT INTO AgLibraryFile VALUES (7, 'file-7', 'photo', 'CR3', 2)"
        )
        db.execute(
            "INSERT INTO AgLibraryFolder VALUES (2, 3, 'Event A')"
        )
        db.execute(
            "INSERT INTO AgLibraryRootFolder VALUES (3, 'Root')"
        )
        db.execute(
            "INSERT INTO Adobe_imageDevelopSettings VALUES (5, 1, ?, '15.4', 'As Shot', 0)",
            ('s = { Exposure2012 = 0.55, Temperature = 5300, Tint = 8, Contrast2012 = 12 }',),
        )


def new_store(tmp_path: Path, monkeypatch) -> LearningProfileStore:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "local-private"))
    return LearningProfileStore(tmp_path / "profiles.sqlite3")


def test_profile_requires_consent_and_valid_identity(tmp_path: Path, monkeypatch):
    store = new_store(tmp_path, monkeypatch)
    with pytest.raises(LearningIntakeError, match="permission"):
        store.create(name="Wedding", photography_type="wedding", color_mode="color", consent=False)
    with pytest.raises(LearningIntakeError, match="name"):
        store.create(name="", photography_type="wedding", color_mode="color", consent=True)
    assert store.list() == []


def test_consistent_catalog_snapshot_and_aggregate_only(tmp_path: Path, monkeypatch):
    store = new_store(tmp_path, monkeypatch)
    catalog = tmp_path / "Finalized Wedding.lrcat"
    make_catalog(catalog)
    before = hashlib.sha256(catalog.read_bytes()).hexdigest()
    profile = store.create(name="Wedding", photography_type="wedding", color_mode="color", consent=True)
    result = store.attach_catalog(profile["profile_id"], catalog_path=str(catalog))
    item = result["catalogs"][0]
    aggregate = item["aggregate"]

    assert result["status"] == "catalog_review"
    assert result["training_ready_samples"] == 0
    assert result["starting_point_verified"] is False
    assert item["source_status"] == "catalog_only_limited"
    assert aggregate["catalog_raw_records"] == 1
    assert aggregate["parsed_raw_records"] == 1
    assert aggregate["candidate_folder_day_groups"] == 1
    assert aggregate["training_ready_samples"] == 0
    assert "file_stem" not in str(aggregate)
    assert hashlib.sha256(catalog.read_bytes()).hexdigest() == before
    assert not list((tmp_path / "local-private" / "learning_intake").glob("pg-lrcat-*"))
    assert len(store.list()) == 1


def test_multiple_catalogs_persist_and_repeat_audit_does_not_duplicate(tmp_path: Path, monkeypatch):
    store = new_store(tmp_path, monkeypatch)
    a = tmp_path / "A.lrcat"
    b = tmp_path / "B.lrcat"
    make_catalog(a)
    make_catalog(b)
    profile_id = store.create(
        name="Event photographer", photography_type="wedding",
        color_mode="black_white", consent=True,
    )["profile_id"]
    store.attach_catalog(profile_id, catalog_path=str(a))
    store.attach_catalog(profile_id, catalog_path=str(b))
    result = store.attach_catalog(profile_id, catalog_path=str(a))
    assert result["color_mode"] == "black_white"
    assert len(result["catalogs"]) == 2
    assert len(LearningProfileStore(store.db_path).get(profile_id)["catalogs"]) == 2


def test_reject_missing_or_wrong_file_without_persisting(tmp_path: Path, monkeypatch):
    store = new_store(tmp_path, monkeypatch)
    profile_id = store.create(
        name="Event photographer", photography_type="wedding",
        color_mode="color", consent=True,
    )["profile_id"]
    invalid = tmp_path / "notes.txt"
    invalid.write_text("not a catalog", encoding="utf-8")
    with pytest.raises(LearningIntakeError):
        store.attach_catalog(profile_id, catalog_path=str(invalid))
    with pytest.raises(LearningIntakeError):
        store.attach_catalog(profile_id, catalog_path=str(tmp_path / "missing.lrcat"))
    assert store.get(profile_id)["catalogs"] == []


def test_smart_preview_link_is_explicitly_unverified(tmp_path: Path, monkeypatch):
    store = new_store(tmp_path, monkeypatch)
    catalog = tmp_path / "Studio.lrcat"
    make_catalog(catalog)
    preview = tmp_path / "Studio Smart Previews.lrdata"
    preview.mkdir()
    profile_id = store.create(
        name="Studio", photography_type="portraits", color_mode="color", consent=True
    )["profile_id"]
    result = store.attach_catalog(
        profile_id, catalog_path=str(catalog), smart_previews_path=str(preview),
    )
    assert result["catalogs"][0]["source_status"] == "smart_previews_unverified"
    assert result["training_ready_samples"] == 0


def test_reject_fake_smart_previews_folder(tmp_path: Path, monkeypatch):
    store = new_store(tmp_path, monkeypatch)
    catalog = tmp_path / "Studio.lrcat"
    make_catalog(catalog)
    fake = tmp_path / "Random Folder"
    fake.mkdir()
    profile_id = store.create(
        name="Studio", photography_type="portraits", color_mode="color", consent=True
    )["profile_id"]
    with pytest.raises(LearningIntakeError, match="Smart Previews"):
        store.attach_catalog(profile_id, catalog_path=str(catalog), smart_previews_path=str(fake))
    assert store.get(profile_id)["catalogs"] == []

def test_catalog_folder_autodetects_exact_sibling(tmp_path: Path, monkeypatch):
    from app.learning_intake.discovery import discover_catalogs
    store = new_store(tmp_path, monkeypatch)
    catalog = tmp_path / "Wedding 2026.lrcat"
    make_catalog(catalog)
    matched = tmp_path / "Wedding 2026 Smart Previews.lrdata"
    matched.mkdir()
    (tmp_path / "Wedding 2026 Previews.lrdata").mkdir()
    (tmp_path / "Other Smart Previews.lrdata").mkdir()

    result = discover_catalogs(str(tmp_path))
    assert result["requires_selection"] is False
    assert result["catalogs"][0]["catalog_path"] == str(catalog.resolve())
    assert result["catalogs"][0]["smart_previews_path"] == str(matched.resolve())
    assert result["catalogs"][0]["preview_detection"] == "name_match_unverified"

    profile_id = store.create(
        name="Wedding", photography_type="wedding",
        color_mode="color", consent=True,
    )["profile_id"]
    saved = store.attach_catalog(profile_id, catalog_path=str(catalog))
    assert saved["catalogs"][0]["smart_previews_path"] == str(matched.resolve())
    assert saved["catalogs"][0]["source_status"] == "smart_previews_unverified"
    assert saved["training_ready_samples"] == 0


def test_discovery_multiple_catalogs_requires_explicit_selection(tmp_path: Path):
    from app.learning_intake.discovery import discover_catalogs
    a, b = tmp_path / "A.lrcat", tmp_path / "B.lrcat"
    make_catalog(a)
    make_catalog(b)
    (tmp_path / "B Smart Previews.lrdata").mkdir()
    result = discover_catalogs(str(tmp_path))
    assert result["requires_selection"] is True
    assert [Path(i["catalog_path"]).name for i in result["catalogs"]] == [
        "A.lrcat", "B.lrcat"
    ]
    assert result["catalogs"][0]["smart_previews_path"] is None
    assert result["catalogs"][1]["smart_previews_path"] is not None


def test_discovery_does_not_guess_wrong_preview_or_recurse(tmp_path: Path):
    from app.learning_intake.discovery import discover_catalogs
    catalog = tmp_path / "My Catalog.lrcat"
    make_catalog(catalog)
    (tmp_path / "Unrelated Smart Previews.lrdata").mkdir()
    (tmp_path / "My Catalog Previews.lrdata").mkdir()
    deeper = tmp_path / "Nested"
    deeper.mkdir()
    (deeper / "My Catalog Smart Previews.lrdata").mkdir()

    result = discover_catalogs(str(catalog))
    assert result["catalogs"][0]["preview_detection"] == "not_found"
    assert result["catalogs"][0]["smart_previews_path"] is None


def test_discovery_rejects_empty_dir_symlinks_and_preview_folder(tmp_path: Path):
    from app.learning_intake.discovery import discover_catalogs
    with pytest.raises(LearningIntakeError, match="No .lrcat"):
        discover_catalogs(str(tmp_path))
    cache = tmp_path / "Demo Smart Previews.lrdata"
    cache.mkdir()
    with pytest.raises(LearningIntakeError, match="catalog folder"):
        discover_catalogs(str(cache))
    bad_link = tmp_path / "linked.lrcat"
    target = tmp_path / "Real.lrcat"
    make_catalog(target)
    try:
        bad_link.symlink_to(target)
    except OSError:
        pytest.skip("Windows symlink creation requires permissions")
    with pytest.raises(LearningIntakeError, match="Symbolic-link"):
        discover_catalogs(str(bad_link))


def test_detection_override_respects_manual_preview_path(tmp_path: Path, monkeypatch):
    store = new_store(tmp_path, monkeypatch)
    catalog = tmp_path / "A.lrcat"
    make_catalog(catalog)
    automatic = tmp_path / "A Smart Previews.lrdata"
    automatic.mkdir()
    manual = tmp_path / "Elsewhere Smart Previews.lrdata"
    manual.mkdir()
    profile_id = store.create(
        name="Wedding", photography_type="wedding",
        color_mode="color", consent=True,
    )["profile_id"]
    result = store.attach_catalog(
        profile_id, catalog_path=str(catalog), smart_previews_path=str(manual),
    )
    assert result["catalogs"][0]["smart_previews_path"] == str(manual.resolve())
    assert result["training_ready_samples"] == 0

def test_delete_profile_removes_only_its_local_metadata(tmp_path: Path, monkeypatch):
    store = new_store(tmp_path, monkeypatch)
    source_a = tmp_path / "Photographer A.lrcat"
    source_b = tmp_path / "Photographer B.lrcat"
    make_catalog(source_a)
    make_catalog(source_b)
    smart = tmp_path / "Photographer A Smart Previews.lrdata"
    smart.mkdir()
    marker = smart / "keep-sources-untouched.txt"
    marker.write_text("must survive", encoding="utf-8")
    raw = tmp_path / "RAW Library"
    raw.mkdir()
    raw_marker = raw / "original.CR3"
    raw_marker.write_bytes(b"not-modified")
    before_catalog = hashlib.sha256(source_a.read_bytes()).hexdigest()
    before_raw = hashlib.sha256(raw_marker.read_bytes()).hexdigest()

    a_id = store.create(
        name="Photographer A", photography_type="wedding",
        color_mode="color", consent=True,
    )["profile_id"]
    b_id = store.create(
        name="Photographer B", photography_type="wedding",
        color_mode="color", consent=True,
    )["profile_id"]
    store.attach_catalog(a_id, catalog_path=str(source_a), raw_fallback_path=str(raw))
    store.attach_catalog(b_id, catalog_path=str(source_b))

    store.delete(a_id)
    with pytest.raises(LearningIntakeError, match="not found"):
        store.get(a_id)
    assert [p["profile_id"] for p in store.list()] == [b_id]
    assert len(store.get(b_id)["catalogs"]) == 1
    assert source_a.is_file() and source_b.is_file()
    assert smart.is_dir() and marker.read_text(encoding="utf-8") == "must survive"
    assert hashlib.sha256(source_a.read_bytes()).hexdigest() == before_catalog
    assert hashlib.sha256(raw_marker.read_bytes()).hexdigest() == before_raw

    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM learning_intake_catalogs WHERE profile_id=?",
            (a_id,),
        ).fetchone()[0] == 0


def test_delete_missing_profile_fails_without_affecting_others(tmp_path: Path, monkeypatch):
    store = new_store(tmp_path, monkeypatch)
    keep = store.create(
        name="Keep", photography_type="wedding",
        color_mode="black_white", consent=True,
    )["profile_id"]
    with pytest.raises(LearningIntakeError, match="not found"):
        store.delete("nonexistent")
    assert store.get(keep)["profile_id"] == keep


HEADERS = {"X-ProGrapher-Secret": "pg-intake-delete-test-secret"}


def test_delete_api_requires_auth_returns_json_and_404(tmp_path: Path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.application import create_app

    # The API creates its own LearningProfileStore() using user_data_dir().
    # Exercise a real single database for setup + HTTP requests. Other tests
    # deliberately inject a separate store.db_path ("profiles.sqlite3"),
    # which is not the API's default "prographer.sqlite3".
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "local-private"))
    store = LearningProfileStore()
    profile_id = store.create(
        name="API", photography_type="wedding",
        color_mode="color", consent=True,
    )["profile_id"]
    untouched_id = store.create(
        name="Keep", photography_type="portraits",
        color_mode="color", consent=True,
    )["profile_id"]
    with TestClient(create_app()) as client:
        route = f"/api/learning-intake/profiles/{profile_id}"
        assert client.delete(route).status_code == 401

        # Prove the profile exists in the API's own database before deleting;
        # a mismatch here must not masquerade as a delete-route failure.
        exists = client.get(route, headers=HEADERS)
        assert exists.status_code == 200, exists.text
        assert exists.json()["profile_id"] == profile_id

        deleted = client.delete(route, headers=HEADERS)
        assert deleted.status_code == 200, deleted.text
        assert deleted.json() == {"deleted": True}

        missing = client.delete(route, headers=HEADERS)
        assert missing.status_code == 404
        assert "not found" in missing.json()["detail"].lower()
        assert client.get(route, headers=HEADERS).status_code == 404
        assert client.get(
            f"/api/learning-intake/profiles/{untouched_id}", headers=HEADERS,
        ).status_code == 200
    assert {p["profile_id"] for p in store.list()} == {untouched_id}
