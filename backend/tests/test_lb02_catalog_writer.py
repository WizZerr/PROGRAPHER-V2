"""Synthetic-only LB-02 tests: a tiny SQLite catalog with Lightroom's Develop tables. No Lightroom involved."""
from __future__ import annotations

import sqlite3
import zlib
from pathlib import Path

import pytest

from app.lightroom_bridge import catalog_writer as writer

# Shape of a Lightroom Classic 15 settings text: byte-sorted keys, nested tables spanning lines, last key has no comma.
SETTINGS = """s = { AILook = {  },
AutoLateralCA = 0,
Blacks2012 = 0,
CameraProfile = "Adobe Standard",
Contrast2012 = 0,
CropLeft = 0.083851,
CropRight = 0.916149,
Exposure2012 = 0,
Highlights2012 = 0,
Look = { Amount = 1,
Group = { ["x-default"] = "Profiles" },
Name = "Adobe Color",
Parameters = { ToneCurvePV2012 = { 0,
0,
255,
255 },
Version = "18.7" } },
ProcessVersion = "15.4",
Shadows2012 = 0,
Temperature = 5150,
Tint = 7,
Version = "18.7",
WhiteBalance = "As Shot",
Whites2012 = 0 }"""
LIGHTROOM_EDIT = """s = { AILook = {  },
AutoLateralCA = 0,
Blacks2012 = 0,
CameraProfile = "Adobe Standard",
Contrast2012 = 0,
CropLeft = 0.083851,
CropRight = 0.916149,
CustomTemperature = 5000,
CustomTint = 10,
Exposure2012 = -0.3,
Highlights2012 = -40,
Look = { Amount = 1,
Group = { ["x-default"] = "Profiles" },
Name = "Adobe Color",
Parameters = { ToneCurvePV2012 = { 0,
0,
255,
255 },
Version = "18.7" } },
ProcessVersion = "15.4",
Shadows2012 = 20,
Temperature = 5000,
Texture = -18,
Tint = 10,
Version = "18.7",
WhiteBalance = "Custom",
Whites2012 = 0 }"""


def _history_blob(text: str) -> bytes:
    raw = text.encode()
    return len(raw).to_bytes(4, "big") + zlib.compress(raw)


def _catalog(path: Path, photos=(("IMG_1", "CR3"), ("IMG_2", "NEF"), ("IMG_3", "JPG"))) -> Path:
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE Adobe_variablesTable (id_local INTEGER PRIMARY KEY, id_global, name, value);
        INSERT INTO Adobe_variablesTable VALUES (1, 'v', 'Adobe_entityIDCounter', 500.0);
        CREATE TABLE Adobe_images (id_local INTEGER PRIMARY KEY, rootFile, masterImage, touchCount, touchTime,
            colorLabels NOT NULL DEFAULT '');
        CREATE TABLE AgLibraryCollection (id_local INTEGER PRIMARY KEY, creationId NOT NULL, genealogy NOT NULL,
            imageCount, name NOT NULL, parent INTEGER, systemOnly NOT NULL);
        INSERT INTO AgLibraryCollection VALUES (7, 'com.adobe.ag.library.collection', '/17', NULL, 'quick collection',
            NULL, 1);
        CREATE TABLE AgLibraryCollectionImage (id_local INTEGER PRIMARY KEY, collection INTEGER NOT NULL,
            image INTEGER NOT NULL, pick NOT NULL, positionInCollection);
        CREATE TABLE AgLibraryFile (id_local INTEGER PRIMARY KEY, baseName, extension);
        CREATE TABLE Adobe_imageDevelopSettings (id_local INTEGER PRIMARY KEY, image, text, digest,
            historySettingsID, hasDevelopAdjustmentsEx, whiteBalance, processVersion);
        CREATE TABLE Adobe_libraryImageDevelopHistoryStep (id_local INTEGER PRIMARY KEY, id_global, dateCreated,
            digest, hasBigData, hasDevelopAdjustments, image, name, relValueString, text, valueString);
        CREATE TABLE LrMobileSyncChangeCounter (id INTEGER PRIMARY KEY, changeCounter);
        INSERT INTO LrMobileSyncChangeCounter VALUES (1, 80);
        CREATE TABLE AgLibraryImageChangeCounter (image INTEGER PRIMARY KEY, changeCounter, lastSyncedChangeCounter,
            changedAtTime, localTimeOffsetSecs);
    """)
    for n, (base, ext) in enumerate(photos, start=1):
        image = 100 + n
        db.execute("INSERT INTO AgLibraryFile VALUES (?, ?, ?)", (10 + n, base, ext))
        db.execute("INSERT INTO Adobe_images VALUES (?, ?, NULL, 1, 0, '')", (image, 10 + n))
        db.execute("INSERT INTO Adobe_imageDevelopSettings VALUES (?, ?, ?, 'old', ?, -1, 'As Shot', '15.4')",
                   (200 + n, image, SETTINGS, f"H{n}"))
        db.execute("INSERT INTO Adobe_libraryImageDevelopHistoryStep VALUES (?, ?, 0, 'old', 0, -1, ?, "
                   "'Import (23/10/2026 12:04:40)', NULL, ?, NULL)", (300 + n, f"H{n}", image, _history_blob(SETTINGS)))
        db.execute("INSERT INTO AgLibraryImageChangeCounter VALUES (?, 1, 0, '', 7200)", (image,))
    db.commit()
    db.close()
    return path


@pytest.fixture(autouse=True)
def _private_data_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def catalog(tmp_path: Path) -> Path:
    return _catalog(tmp_path / "Wedding.lrcat")


def _row(catalog: Path, image: int):
    db = sqlite3.connect(catalog)
    try:
        return db.execute("SELECT text, digest, historySettingsID, whiteBalance FROM Adobe_imageDevelopSettings "
                          "WHERE image = ?", (image,)).fetchone()
    finally:
        db.close()


def test_settings_round_trip_keeps_nested_tables():
    entries, trailer = writer.parse_settings(SETTINGS + "\n")
    assert [k for k, _ in entries][:3] == ["AILook", "AutoLateralCA", "Blacks2012"]
    assert "Look" in dict(entries) and trailer == "\n"
    assert writer.set_settings(SETTINGS, {}) == SETTINGS


def test_set_settings_reproduces_lightroom_own_edit():
    values = writer.normalize_edit({"Exposure2012": -0.3, "Highlights2012": -40, "Shadows2012": 20,
                                    "Texture": -18, "Temperature": 5000, "Tint": 10}, is_raw=True)
    assert writer.set_settings(SETTINGS, values) == LIGHTROOM_EDIT


def test_normalize_rejects_bad_values_and_drops_white_balance_for_jpeg():
    with pytest.raises(ValueError):
        writer.normalize_edit({"Exposure2012": 9}, is_raw=True)
    with pytest.raises(ValueError):
        writer.normalize_edit({"CropLeft": 0.1}, is_raw=True)
    with pytest.raises(ValueError):
        writer.normalize_edit({"Temperature": 5000}, is_raw=True)
    assert writer.normalize_edit({"Temperature": 5000, "Tint": 3, "Exposure2012": 0.333}, is_raw=False) == {
        "Exposure2012": 0.33}


def test_write_edits_writes_like_lightroom(catalog: Path, tmp_path: Path):
    report = writer.write_edits(catalog, {101: {"Exposure2012": 0.5, "Temperature": 6500, "Tint": 15}},
                                backup_dir=tmp_path / "backups")
    assert [w["image"] for w in report["written"]] == [101] and report["skipped"] == []
    text, digest, history_id, white_balance = _row(catalog, 101)
    values = writer.read_settings(text)
    assert values["Exposure2012"] == "0.5" and values["WhiteBalance"] == '"Custom"'
    assert values["CustomTemperature"] == "6500" and values["CropLeft"] == "0.083851"
    assert digest != "old" and len(digest) == 32 and white_balance == "Custom"
    db = sqlite3.connect(catalog)
    step = db.execute("SELECT id_local, id_global, digest, name, text FROM Adobe_libraryImageDevelopHistoryStep "
                      "WHERE image = 101 ORDER BY id_local DESC").fetchone()
    assert step[0] == 501 and step[1] == history_id and step[2] == digest and step[3] == "ProGrapher"
    assert zlib.decompress(step[4][4:]).decode() == text
    assert db.execute("SELECT value FROM Adobe_variablesTable WHERE name='Adobe_entityIDCounter'").fetchone()[0] == 501
    assert db.execute("SELECT changeCounter FROM LrMobileSyncChangeCounter").fetchone()[0] == 81
    assert db.execute("SELECT changeCounter FROM AgLibraryImageChangeCounter WHERE image=101").fetchone()[0] == 81
    assert db.execute("SELECT touchCount FROM Adobe_images WHERE id_local=101").fetchone()[0] == 2
    db.close()
    assert _row(catalog, 102)[0] == SETTINGS  # untouched photo stays untouched


def test_refuses_while_lightroom_is_open(catalog: Path):
    Path(f"{catalog}.lock").write_text("")
    with pytest.raises(writer.CatalogWriteError):
        writer.write_edits(catalog, {101: {"Exposure2012": 0.5}})
    assert _row(catalog, 101)[0] == SETTINGS


def test_invalid_value_writes_nothing(catalog: Path, tmp_path: Path):
    with pytest.raises(ValueError):
        writer.write_edits(catalog, {101: {"Exposure2012": 0.5}, 102: {"Exposure2012": 99}},
                           backup_dir=tmp_path / "backups")
    assert _row(catalog, 101)[0] == SETTINGS
    assert not (tmp_path / "backups").exists()


def test_photographer_edits_are_protected_unless_asked(catalog: Path, tmp_path: Path):
    db = sqlite3.connect(catalog)
    db.execute("INSERT INTO Adobe_libraryImageDevelopHistoryStep (id_local, image, name) VALUES (400, 102, 'Exposure')")
    db.commit()
    db.close()
    report = writer.write_edits(catalog, {102: {"Exposure2012": 1}, 999: {"Exposure2012": 1}},
                                backup_dir=tmp_path / "b")
    assert report["written"] == [] and report["backup"] is None
    assert {s["reason"] for s in report["skipped"]} == {"edited_by_photographer", "not_in_catalog"}
    report = writer.write_edits(catalog, {102: {"Exposure2012": 1}}, overwrite_photographer_edits=True,
                                backup_dir=tmp_path / "b")
    assert report["written"][0]["image"] == 102


def test_rerun_after_prographer_step_is_allowed(catalog: Path, tmp_path: Path):
    writer.write_edits(catalog, {101: {"Exposure2012": 0.5}}, backup_dir=tmp_path / "b")
    report = writer.write_edits(catalog, {101: {"Exposure2012": 0.7}}, backup_dir=tmp_path / "b")
    assert report["written"] and writer.read_settings(_row(catalog, 101)[0])["Exposure2012"] == "0.7"


def test_jpeg_gets_tone_but_not_white_balance(catalog: Path, tmp_path: Path):
    writer.write_edits(catalog, {103: {"Exposure2012": 0.2, "Temperature": 6000, "Tint": 5}},
                       backup_dir=tmp_path / "b")
    values = writer.read_settings(_row(catalog, 103)[0])
    assert values["Exposure2012"] == "0.2" and values["WhiteBalance"] == '"As Shot"'


def test_old_process_version_is_skipped(catalog: Path, tmp_path: Path):
    db = sqlite3.connect(catalog)
    db.execute("UPDATE Adobe_imageDevelopSettings SET processVersion = '5.0' WHERE image = 101")
    db.commit()
    db.close()
    report = writer.write_edits(catalog, {101: {"Exposure2012": 0.5}}, backup_dir=tmp_path / "b")
    assert report["skipped"][0]["reason"] == "old_or_unknown_process_version"


def test_backup_restores_the_catalog(catalog: Path, tmp_path: Path):
    report = writer.write_edits(catalog, {101: {"Exposure2012": 0.5}}, backup_dir=tmp_path / "b")
    backup = Path(report["backup"])
    assert backup.suffix == ".lrcat-backup"
    writer.restore_backup(backup, catalog)
    assert _row(catalog, 101)[:2] == (SETTINGS, "old")


def test_unsupported_catalog_is_refused(tmp_path: Path):
    path = tmp_path / "Other.lrcat"
    sqlite3.connect(path).execute("CREATE TABLE Adobe_images (id_local INTEGER PRIMARY KEY)").connection.close()
    with pytest.raises(writer.CatalogWriteError):
        writer.write_edits(path, {1: {"Exposure2012": 0.5}})


def test_mark_photos_adds_collection_and_labels(catalog: Path, tmp_path: Path):
    db = sqlite3.connect(catalog)
    db.execute("UPDATE Adobe_images SET colorLabels = 'Red' WHERE id_local = 102")
    db.commit()
    db.close()
    report = writer.mark_photos(catalog, [101, 102, 999], backup_dir=tmp_path / "b")
    assert report["marked"] == [101, 102] and report["labelled"] == [101] and report["not_in_catalog"] == [999]
    db = sqlite3.connect(catalog)
    coll = db.execute("SELECT id_local, creationId, genealogy, name, parent, systemOnly FROM AgLibraryCollection "
                      "WHERE name = ?", (writer.ANCHOR_COLLECTION,)).fetchone()
    assert coll == (501, "com.adobe.ag.library.collection", "/3501", writer.ANCHOR_COLLECTION, None, 0)
    assert [r[0] for r in db.execute("SELECT image FROM AgLibraryCollectionImage WHERE collection = 501")] == [101, 102]
    assert dict(db.execute("SELECT id_local, colorLabels FROM Adobe_images")) == {101: "Purple", 102: "Red", 103: ""}
    assert db.execute("SELECT value FROM Adobe_variablesTable WHERE name='Adobe_entityIDCounter'").fetchone()[0] == 503
    db.close()


def test_mark_photos_reuses_only_an_owned_untouched_collection(catalog: Path, tmp_path: Path):
    first = writer.mark_photos(catalog, [101, 102], backup_dir=tmp_path / "b")
    again = writer.mark_photos(catalog, [103], owned_collection=first["collection"], expected_members=[101, 102],
                               backup_dir=tmp_path / "b")
    assert again["collection"] == first["collection"] and not again["created"]
    db = sqlite3.connect(catalog)
    assert writer.collection_members(db, first["collection"]) == [103]
    db.close()
    empty = writer.mark_photos(catalog, [424242], backup_dir=tmp_path / "b")
    assert empty["collection"] is None and empty["collection_name"] is None and empty["created"] is False
    db = sqlite3.connect(catalog)
    db.close()


def test_mark_photos_never_touches_the_photographers_collections(catalog: Path, tmp_path: Path):
    db = sqlite3.connect(catalog)
    db.execute("INSERT INTO AgLibraryCollection VALUES (90, 'com.adobe.ag.library.collection', '/290', NULL, ?, "
               "NULL, 0)", (writer.ANCHOR_COLLECTION,))
    db.execute("INSERT INTO AgLibraryCollectionImage VALUES (91, 90, 103, 0, NULL)")
    db.commit()
    db.close()
    ours = writer.mark_photos(catalog, [101], backup_dir=tmp_path / "b")
    assert ours["created"] and ours["collection"] != 90
    assert ours["collection_name"] == f"{writer.ANCHOR_COLLECTION} (2)"
    # the photographer changed our collection: re-marking makes a new one and leaves theirs as it is
    db = sqlite3.connect(catalog)
    db.execute("INSERT INTO AgLibraryCollectionImage VALUES (92, ?, 102, 0, NULL)", (ours["collection"],))
    db.commit()
    db.close()
    again = writer.mark_photos(catalog, [103], collection_name=ours["collection_name"],
                               owned_collection=ours["collection"], expected_members=[101], backup_dir=tmp_path / "b")
    assert again["created"] and again["collection"] != ours["collection"]
    db = sqlite3.connect(catalog)
    assert writer.collection_members(db, 90) == [103]
    assert sorted(writer.collection_members(db, ours["collection"])) == [101, 102]
    db.close()


def test_mark_photos_refuses_while_open(catalog: Path):
    Path(f"{catalog}.lock").write_text("")
    with pytest.raises(writer.CatalogWriteError):
        writer.mark_photos(catalog, [101])


def _digest(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_photos_outside_the_allow_list_stop_the_write(catalog: Path, tmp_path: Path):
    before = _digest(catalog)
    with pytest.raises(writer.CatalogWriteError):
        writer.write_edits(catalog, {101: {"Exposure2012": 0.5}, 102: {"Exposure2012": 0.5}}, allowed_images={101},
                           backup_dir=tmp_path / "b")
    assert _digest(catalog) == before


def test_two_writers_on_one_catalog_are_refused(catalog: Path, tmp_path: Path):
    with writer.catalog_lock(catalog):
        with pytest.raises(writer.CatalogWriteError, match="already writing"):
            writer.write_edits(catalog, {101: {"Exposure2012": 0.5}}, backup_dir=tmp_path / "b")
    assert writer.write_edits(catalog, {101: {"Exposure2012": 0.5}}, backup_dir=tmp_path / "b")["written"]


def test_lightroom_opening_during_the_write_rolls_back(catalog: Path, tmp_path: Path, monkeypatch):
    before = _digest(catalog)
    calls = iter([False, False, False, True])  # closed for the checks before writing, open just before COMMIT
    monkeypatch.setattr(writer, "catalog_in_use", lambda _c: next(calls, True))
    with pytest.raises(writer.CatalogWriteError, match="opened"):
        writer.write_edits(catalog, {101: {"Exposure2012": 0.5}}, backup_dir=tmp_path / "b")
    assert _digest(catalog) == before


def test_failure_in_the_middle_leaves_the_catalog_untouched(catalog: Path, tmp_path: Path, monkeypatch):
    before = _digest(catalog)
    real, seen = writer._encode_history, []

    def flaky(method, text):
        seen.append(1)
        if len(seen) == 2:
            raise RuntimeError("simulated crash in the middle of the write")
        return real(method, text)
    monkeypatch.setattr(writer, "_encode_history", flaky)
    with pytest.raises(RuntimeError):
        writer.write_edits(catalog, {101: {"Exposure2012": 0.5}, 102: {"Exposure2012": 0.5}}, backup_dir=tmp_path / "b")
    assert _digest(catalog) == before


def test_revert_puts_back_only_photos_untouched_since(catalog: Path, tmp_path: Path):
    result = writer.write_edits(catalog, {101: {"Exposure2012": 0.5}, 102: {"Exposure2012": 0.5}},
                                backup_dir=tmp_path / "b")
    # the photographer edits 102 in Lightroom afterwards
    db = sqlite3.connect(catalog)
    text = db.execute("SELECT text FROM Adobe_imageDevelopSettings WHERE image = 102").fetchone()[0]
    db.execute("UPDATE Adobe_imageDevelopSettings SET text = ?, historySettingsID = 'LR-NEW' WHERE image = 102",
               (writer.set_settings(text, {"Exposure2012": 0.9}),))
    db.execute("INSERT INTO Adobe_libraryImageDevelopHistoryStep (id_local, id_global, image, name) "
               "VALUES (9000, 'LR-NEW', 102, 'Exposure')")
    db.commit()
    db.close()
    undo = writer.revert_edits(catalog, result["written"], backup_dir=tmp_path / "b")
    assert undo["reverted"] == [101] and undo["kept"] == [{"image": 102, "reason": "changed_after_prographer"}]
    assert _row(catalog, 101)[:3] == (SETTINGS, "old", "H1")
    assert writer.read_settings(_row(catalog, 102)[0])["Exposure2012"] == "0.9"
    db = sqlite3.connect(catalog)
    assert db.execute("SELECT COUNT(*) FROM Adobe_libraryImageDevelopHistoryStep WHERE image = 101 AND "
                      "name = 'ProGrapher'").fetchone()[0] == 0
    db.close()
