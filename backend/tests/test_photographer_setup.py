import sqlite3
from pathlib import Path

from app.photographer.lightroom import probe_catalog
from app.photographer.setup_store import PhotographerSetupStore
from app.services.photographer_setup_service import choose_catalog


def make_catalog(path: Path, image_count: int = 3) -> None:
    with sqlite3.connect(path) as db:
        db.execute(
            """
            CREATE TABLE Adobe_images (
                id_local INTEGER PRIMARY KEY
            )
            """
        )
        db.executemany(
            "INSERT INTO Adobe_images(id_local) VALUES (?)",
            [(index,) for index in range(1, image_count + 1)],
        )


def test_catalog_probe_reads_lightroom_catalog_read_only(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "Wedding Catalog.lrcat"
    make_catalog(catalog, image_count=4)

    result = probe_catalog(catalog)

    assert result.exists is True
    assert result.readable is True
    assert result.sqlite_valid is True
    assert result.catalog_photo_records == 4
    assert "אינו מספר עריכות סופיות" in result.note


def test_selected_catalog_is_persisted(tmp_path: Path) -> None:
    catalog = tmp_path / "קטלוג חתונות.lrcat"
    make_catalog(catalog)

    store = PhotographerSetupStore(tmp_path / "state.sqlite3")
    overview = choose_catalog(str(catalog), store=store)

    assert overview.setup.catalog_path == str(catalog.resolve())
    assert overview.setup.status == "data_review"

    loaded = store.get()
    assert loaded.catalog_path == str(catalog.resolve())


def test_non_catalog_file_is_rejected(tmp_path: Path) -> None:
    wrong = tmp_path / "not-a-catalog.txt"
    wrong.write_text("hello", encoding="utf-8")

    result = probe_catalog(wrong)

    assert result.sqlite_valid is False
    assert ".lrcat" in result.note
