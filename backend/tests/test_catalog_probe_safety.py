"""Stage 1 safety regressions. All catalogs are disposable synthetic fixtures."""
from pathlib import Path
import sqlite3

from app.photographer.lightroom import probe_catalog


def create_catalog(path: Path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE Adobe_images(id_local INTEGER PRIMARY KEY)")
        db.execute("INSERT INTO Adobe_images VALUES (1)")
    return path


def test_readonly_catalog_probe_keeps_bytes_unchanged(tmp_path: Path):
    catalog = create_catalog(tmp_path / "copy.lrcat")
    before = catalog.read_bytes()
    result = probe_catalog(catalog)
    assert result.readable and result.sqlite_valid and result.catalog_photo_records == 1
    assert catalog.read_bytes() == before


def test_live_catalog_sidecars_fail_closed(tmp_path: Path):
    catalog = create_catalog(tmp_path / "copy.lrcat")
    for suffix in ("-wal", "-shm", ".lock"):
        sidecar = Path(str(catalog) + suffix)
        sidecar.write_bytes(b"not a finalized snapshot")
        result = probe_catalog(catalog)
        assert not result.readable and not result.sqlite_valid
        sidecar.unlink()


def test_missing_schema_fails_closed(tmp_path: Path):
    catalog = tmp_path / "unknown.lrcat"
    with sqlite3.connect(catalog) as db:
        db.execute("CREATE TABLE something_else(id INTEGER)")
    result = probe_catalog(catalog)
    assert not result.sqlite_valid


def test_corrupt_sqlite_fails_closed(tmp_path: Path):
    catalog = tmp_path / "damaged.lrcat"
    catalog.write_bytes(b"not SQLite")
    result = probe_catalog(catalog)
    assert not result.readable and not result.sqlite_valid
