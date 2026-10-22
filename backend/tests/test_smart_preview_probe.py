"""Read-only Smart Preview DNG probe tests; not proof of LR identity."""
from pathlib import Path
import json
import sqlite3

import pytest

from app.learning_intake.smart_preview_probe import inspect_smart_previews
from app.learning_intake import smart_preview_probe as probe
from app.learning_intake.service import LearningIntakeError, LearningProfileStore


def catalog_fixture(path: Path):
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE Adobe_images(id_local INTEGER PRIMARY KEY,id_global TEXT,rootFile INTEGER,fileFormat TEXT,captureTime TEXT,originalCaptureTime TEXT,masterImage INTEGER,copyName TEXT);
        CREATE TABLE AgLibraryFile(id_local INTEGER PRIMARY KEY,id_global TEXT,baseName TEXT,extension TEXT,folder INTEGER);
        CREATE TABLE AgLibraryFolder(id_local INTEGER PRIMARY KEY,rootFolder INTEGER,pathFromRoot TEXT);
        CREATE TABLE AgLibraryRootFolder(id_local INTEGER PRIMARY KEY,name TEXT);
        CREATE TABLE Adobe_imageDevelopSettings(id_local INTEGER PRIMARY KEY,image INTEGER,text TEXT,processVersion TEXT,whiteBalance TEXT,grayscale INTEGER);
        """)
        db.execute("INSERT INTO AgLibraryRootFolder VALUES(1,'test')")
        db.execute("INSERT INTO AgLibraryFolder VALUES(2,1,'event')")
        db.execute("INSERT INTO AgLibraryFile VALUES(3,'f','photo','cr3',2)")
        db.execute("INSERT INTO Adobe_images VALUES(5,'p',3,'RAW','2026-09-20',NULL,NULL,NULL)")
        db.execute("INSERT INTO Adobe_imageDevelopSettings VALUES(4,5,'s={ Exposure2012=0.3 }','15.4','As Shot',0)")


def test_smart_preview_dng_inventory_and_decode_is_not_identity(tmp_path, monkeypatch):
    root = tmp_path / "Test Smart Previews.lrdata"
    root.mkdir()
    (root / "a.dng").write_bytes(b"II*\\x00".replace(b"\\x00", b"\x00") + b"synthetic")
    (root / "bad.dng").write_bytes(b"wrong")
    (root / "cache.txt").write_text("test")
    monkeypatch.setattr(probe, "_decode_sample", lambda file: {
        "state": "decoded_unverified", "width": 2560, "height": 1707,
        "preview_mean_luma": 0.4,
    })
    report = inspect_smart_previews(root)
    assert report["counts"]["dng_tiff_signature_candidates"] == 1
    assert report["counts"]["invalid_dng_container_signature"] == 1
    assert report["decode_status_counts"]["decoded_unverified"] == 1
    assert report["training_ready_samples"] == 0
    assert not report["photo_to_dng_link_verified"]
    assert str(root) not in json.dumps(report)


def test_smart_preview_rejects_wrong_root_and_excessive_limit(tmp_path):
    wrong = tmp_path / "Ordinary Previews.lrdata"
    wrong.mkdir()
    with pytest.raises(LearningIntakeError, match="Smart Previews"):
        inspect_smart_previews(wrong)
    root = tmp_path / "Test Smart Previews.lrdata"
    root.mkdir()
    with pytest.raises(LearningIntakeError):
        inspect_smart_previews(root, decode_limit=5)


def test_scoped_profile_smart_preview_probe_and_api_auth(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.application import create_app
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", "preview-test-secret")
    catalog = tmp_path / "Pilot.lrcat"
    catalog_fixture(catalog)
    smart = tmp_path / "Pilot Smart Previews.lrdata"
    smart.mkdir()
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding", color_mode="color", consent=True)
    other = store.create(name="Other", photography_type="wedding", color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    with pytest.raises(LearningIntakeError, match="not linked"):
        store.probe_smart_previews(other["profile_id"], catalog_path=str(catalog))
    endpoint = f"/api/learning-intake/profiles/{owner['profile_id']}/smart-preview-probe"
    with TestClient(create_app()) as client:
        assert client.post(endpoint, json={"catalog_path": str(catalog)}).status_code == 401
        response = client.post(endpoint, json={"catalog_path": str(catalog)},
                               headers={"X-ProGrapher-Secret": "preview-test-secret"})
        assert response.status_code == 200, response.text
        assert response.json()["decode_attempts"] == 0
        assert response.json()["training_ready_samples"] == 0
        assert not response.json()["photo_to_dng_link_verified"]


def test_sdk_link_correlates_catalog_uuid_and_smart_dng_but_never_trains(tmp_path, monkeypatch):
    from app.learning_intake.sdk_link_review import verify_link_export
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "private"))
    catalog = tmp_path / "Pilot.lrcat"
    catalog_fixture(catalog)
    smart = tmp_path / "Pilot Smart Previews.lrdata"
    smart.mkdir()
    dng = smart / "sdk-generated-name.dng"
    dng.write_bytes(b"II*\x00" + b"synthetic")
    evidence = tmp_path / "sdk-links.json"
    evidence.write_text(json.dumps({
        "schema": "prographer.lightroom.smart_preview_sdk_links.v1",
        "catalog_path": str(catalog),
        "records": [{
            "photo_uuid": "p",
            "smart_preview_path": str(dng),
            "is_virtual_copy": False,
        }],
    }), encoding="utf-8")
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding",
                         color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    result = store.review_smart_preview_sdk_links(
        owner["profile_id"], catalog_path=str(catalog), evidence_path=str(evidence)
    )
    assert result["sdk_path_catalog_uuid_correlated"] == 1
    assert result["training_ready_samples"] == 0
    assert result["source_raw_identity_verified"] is False
    assert result["approved_finality_verified"] is False
    assert result["records"][0]["training_eligible"] is False


def test_sdk_link_rejects_foreign_paths_and_catalogs(tmp_path, monkeypatch):
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "private"))
    catalog = tmp_path / "Pilot.lrcat"
    catalog_fixture(catalog)
    smart = tmp_path / "Pilot Smart Previews.lrdata"
    smart.mkdir()
    foreign = tmp_path / "foreign.dng"
    foreign.write_bytes(b"II*\x00" + b"synthetic")
    evidence = tmp_path / "foreign.json"
    data = {
        "schema": "prographer.lightroom.smart_preview_sdk_links.v1",
        "catalog_path": str(catalog),
        "records": [{"photo_uuid": "p", "smart_preview_path": str(foreign)}],
    }
    evidence.write_text(json.dumps(data), encoding="utf-8")
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding",
                         color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    review = store.review_smart_preview_sdk_links(
        owner["profile_id"], catalog_path=str(catalog), evidence_path=str(evidence)
    )
    assert review["status_counts"]["outside_selected_smart_preview_root"] == 1
    assert review["sdk_path_catalog_uuid_correlated"] == 0
    data["catalog_path"] = str(tmp_path / "Other.lrcat")
    evidence.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(LearningIntakeError):
        store.review_smart_preview_sdk_links(
            owner["profile_id"], catalog_path=str(catalog), evidence_path=str(evidence)
        )


def test_sdk_link_duplicate_photo_uuid_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "private"))
    catalog = tmp_path / "Pilot.lrcat"
    catalog_fixture(catalog)
    smart = tmp_path / "Pilot Smart Previews.lrdata"
    smart.mkdir()
    evidence = tmp_path / "dupes.json"
    row = {"photo_uuid": "p", "smart_preview_path": None}
    evidence.write_text(json.dumps({
        "schema": "prographer.lightroom.smart_preview_sdk_links.v1",
        "catalog_path": str(catalog),
        "records": [row, row],
    }), encoding="utf-8")
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding",
                         color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    with pytest.raises(LearningIntakeError, match="Duplicate"):
        store.review_smart_preview_sdk_links(
            owner["profile_id"], catalog_path=str(catalog), evidence_path=str(evidence)
        )
