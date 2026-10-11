"""RAW-CAT-01E.04A: synthetic preview index probes; no real photographer data."""
import json
from pathlib import Path
import sqlite3

import pytest

from app.photographer.lightroom_preview_index import (
    PreviewIndexError, inspect_preview_index, main,
)


def make_fixture(tmp_path: Path) -> tuple[Path, Path]:
    catalog = tmp_path / "SYNTH.lrcat"
    with sqlite3.connect(catalog) as db:
        db.execute("CREATE TABLE Adobe_images(id_local INTEGER, id_global INTEGER, fileFormat TEXT)")
        db.executemany("INSERT INTO Adobe_images VALUES (?,?,?)", [
            (1, 101, "RAW"), (2, 102, "RAW"), (3, 103, "JPEG"), (4, 104, "RAW")
        ])
    root = tmp_path / "SYNTH Previews.lrdata"
    root.mkdir()
    with sqlite3.connect(root / "previews.db") as db:
        db.execute("CREATE TABLE ImageCacheEntry(imageId INTEGER, uuid TEXT, digest TEXT, orientation INTEGER)")
        db.execute("CREATE TABLE Pyramid(uuid TEXT, digest TEXT)")
        db.execute("CREATE TABLE PyramidLevel(uuid TEXT, digest TEXT, level INTEGER)")
        db.executemany("INSERT INTO ImageCacheEntry VALUES (?,?,?,?)", [
            (1, "u1", "d1", 0), (2, "u2", "d2", 0), (3, "u3", "d3", 0),
            (999, "u4", "d4", 0), (1, "u5", "d5", 0),
        ])
        db.executemany("INSERT INTO Pyramid VALUES (?,?)", [
            ("u1", "d1"), ("u2", "d2"), ("u3", "d3"), ("u4", "d4"),
        ])
        db.executemany("INSERT INTO PyramidLevel VALUES (?,?,?)", [
            ("u1", "d1", 1), ("u2", "d2", 1), ("u4", "d4", 1),
            ("u4", "d4", 2),
        ])
    (root / "a").mkdir()
    (root / "a" / "PRIVATE_PREVIEW_NAME").write_bytes(b"\xff\xd8\xff" + b"synthetic")
    (root / "a" / "NON_JPEG").write_bytes(b"abc")
    return catalog, root


def test_preview_index_counts_and_no_private_data(tmp_path):
    catalog, root = make_fixture(tmp_path)
    before_cat = catalog.read_bytes()
    before_db = (root / "previews.db").read_bytes()
    report = inspect_preview_index(catalog, root)
    assert report["catalog_counts"] == {"all_photo_rows": 4, "raw_photo_rows": 3}
    assert report["preview_file_signatures"] == {
        "jpeg_signature_files": 1, "other_signature_files": 1,
    }
    assert report["image_cache"] == {
        "entry_rows": 5, "distinct_nonnull_image_ids": 4,
        "null_image_id_rows": 0, "duplicate_image_id_extra_rows": 1,
    }
    overlaps = report["candidate_id_overlaps"]
    assert overlaps["catalog_id_local_raw"] == 2
    assert overlaps["catalog_id_global_raw"] == 0
    assert overlaps["catalog_id_local_all"] == 3
    assert overlaps["raw_catalog_ids_without_local_cache_match"] == 1
    link = report["pyramid_linkage"]
    assert link["cache_rows_exactly_one_pyramid"] == 4
    assert link["cache_rows_no_pyramid"] == 1
    assert link["cache_rows_one_pyramid_with_level"] == 3
    assert link["level_rows"] == 4
    assert report["training_ready_samples"] == 0
    assert not report["physical_jpeg_to_photo_link_verified"]
    serialized = json.dumps(report)
    assert "PRIVATE_PREVIEW_NAME" not in serialized
    assert "SYNTH" not in serialized
    assert catalog.read_bytes() == before_cat
    assert (root / "previews.db").read_bytes() == before_db


def test_empty_cache_stays_unverified(tmp_path):
    catalog, root = make_fixture(tmp_path)
    with sqlite3.connect(root / "previews.db") as db:
        db.execute("DELETE FROM ImageCacheEntry")
    report = inspect_preview_index(catalog, root)
    assert report["candidate_id_overlaps"]["interpretation"] == "NO_RAW_KEY_OVERLAP"
    assert report["pyramid_linkage"]["cache_rows_no_pyramid"] == 0


def test_wrong_schema_rejected_instead_of_guessing(tmp_path):
    catalog, root = make_fixture(tmp_path)
    with sqlite3.connect(root / "previews.db") as db:
        db.execute("DROP TABLE PyramidLevel")
    with pytest.raises(PreviewIndexError, match="PyramidLevel"):
        inspect_preview_index(catalog, root)


def test_nonempty_wal_rejected(tmp_path):
    catalog, root = make_fixture(tmp_path)
    (root / "previews.db-wal").write_bytes(b"not finalized")
    with pytest.raises(PreviewIndexError, match="WAL"):
        inspect_preview_index(catalog, root)


def test_report_cannot_be_written_inside_cache(tmp_path, monkeypatch):
    catalog, root = make_fixture(tmp_path)
    monkeypatch.setattr("sys.argv", [
        "preview_probe", "--catalog", str(catalog),
        "--previews-dir", str(root), "--report", str(root / "bad.json"),
    ])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert not (root / "bad.json").exists()
