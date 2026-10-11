"""Synthetic RAW disk/catalog name-join audit tests. No photographer data."""
import json
import sqlite3
import pytest
from app.photographer.raw_disk_catalog_audit import audit


def _catalog(path, rows):
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE Adobe_images(id_local INTEGER PRIMARY KEY, id_global TEXT, rootFile INTEGER, fileFormat TEXT,
          captureTime TEXT, originalCaptureTime TEXT, masterImage INTEGER, copyName TEXT);
        CREATE TABLE AgLibraryFile(id_local INTEGER PRIMARY KEY, id_global TEXT, baseName TEXT, extension TEXT, folder INTEGER);
        CREATE TABLE AgLibraryFolder(id_local INTEGER PRIMARY KEY, rootFolder INTEGER, pathFromRoot TEXT);
        CREATE TABLE AgLibraryRootFolder(id_local INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE Adobe_imageDevelopSettings(id_local INTEGER PRIMARY KEY, image INTEGER, text TEXT, processVersion TEXT,
          whiteBalance TEXT, grayscale INTEGER);
        """)
        db.execute("INSERT INTO AgLibraryRootFolder VALUES(1,'PRIVATE_ROOT')")
        db.execute("INSERT INTO AgLibraryFolder VALUES(1,1,'PRIVATE_EVENT')")
        for i, (stem, ext) in enumerate(rows, start=1):
            db.execute("INSERT INTO AgLibraryFile VALUES(?,?,?,?,?)", (i,f"f{i}",stem,ext,1))
            db.execute("INSERT INTO Adobe_images VALUES(?,?,?,?,?,?,?,?)",
                       (i,f"i{i}",i,"RAW","2026-02-01 12:12",None,None,None))
            db.execute("INSERT INTO Adobe_imageDevelopSettings VALUES(?,?,?,?,?,?)",
                       (i,i,"s = { Exposure2012 = 1 }","15.4","As Shot",0))


def test_unique_candidates_and_aggregate_privacy(tmp_path):
    raw=tmp_path/"raw";raw.mkdir()
    (raw/"PRIVATE_A.CR3").write_bytes(b"fake")
    (raw/"._PRIVATE_B.CR3").write_bytes(b"mac metadata")
    (raw/"OTHER.JPG").write_bytes(b"jpeg")
    cat=tmp_path/"export.lrcat";_catalog(cat,[("PRIVATE_A","cr3"),("PRIVATE_B","cr3")])
    report=audit(raw,cat)
    assert report["disk"]["raw_files"]==1
    assert report["disk"]["mac_metadata_skipped"]==1
    assert report["name_join"]["name_only_candidate_pairs"]==1
    assert report["name_join"]["unmatched_catalog_rows"]==1
    assert report["training_eligible_pairs"]==0
    text=json.dumps(report)
    assert "PRIVATE_A" not in text and "PRIVATE_ROOT" not in text and str(tmp_path) not in text


def test_duplicate_files_and_catalog_rows_quarantined(tmp_path):
    raw=tmp_path/"raw";raw.mkdir()
    child=raw/"child";child.mkdir()
    (raw/"PRIVATE_A.CR3").write_bytes(b"x")
    (child/"private_a.cr3").write_bytes(b"y")
    cat=tmp_path/"export.lrcat";_catalog(cat,[("PRIVATE_A","cr3"),("PRIVATE_A","cr3")])
    report=audit(raw,cat)
    assert report["name_join"]["name_only_candidate_pairs"]==0
    assert report["name_join"]["ambiguous_keys"]==1
    assert report["name_join"]["ambiguous_disk_files"]==2


def test_extension_is_part_of_match_key(tmp_path):
    raw=tmp_path/"raw";raw.mkdir()
    (raw/"PRIVATE_A.NEF").write_bytes(b"x")
    cat=tmp_path/"export.lrcat";_catalog(cat,[("PRIVATE_A","cr3")])
    report=audit(raw,cat)
    assert report["name_join"]["name_only_candidate_pairs"]==0
    assert report["name_join"]["unmatched_disk_raw"]==1
    assert report["name_join"]["unmatched_catalog_rows"]==1


def test_live_catalog_wal_rejected(tmp_path):
    raw=tmp_path/"raw";raw.mkdir()
    cat=tmp_path/"export.lrcat";_catalog(cat,[("PRIVATE_A","cr3")])
    (tmp_path/"export.lrcat-wal").write_bytes(b"live")
    with pytest.raises(Exception,match="WAL"):
        audit(raw,cat)
