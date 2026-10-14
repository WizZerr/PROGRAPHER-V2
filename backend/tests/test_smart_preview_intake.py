from pathlib import Path
import os
import sqlite3

import pytest

from app.photographer.smart_preview_probe import probe_smart_previews
from app.photographer.setup_store import PhotographerSetupStore
from app.services.photographer_setup_service import choose_catalog, choose_smart_previews


def catalog_fixture(path: Path) -> Path:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE Adobe_images (id_local INTEGER PRIMARY KEY)")
        db.execute("INSERT INTO Adobe_images VALUES (1)")
    return path


def preview_fixture(tmp_path: Path, basename: str = "Wedding Smart Previews.lrdata") -> Path:
    directory = tmp_path / basename
    (directory / "one").mkdir(parents=True)
    # This is a synthetic INVENTORY fixture, not an Adobe Smart Preview file.
    (directory / "one" / "synthetic.bin").write_bytes(b"synthetic")
    return directory


def test_preview_inventory_is_not_identity_or_training_proof(tmp_path: Path):
    catalog = catalog_fixture(tmp_path / "Wedding.lrcat")
    previews = preview_fixture(tmp_path)
    result = probe_smart_previews(previews, catalog_path=catalog)
    assert result.exists and result.readable
    assert result.asset_files == 1 and result.total_bytes == 9
    assert result.name_matches_catalog is True
    assert result.identity_verified is False
    assert "NOT verified" in result.note


@pytest.mark.parametrize("folder", ["Wedding Previews.lrdata", "Other Smart Previews.lrdata", "random"])
def test_rejects_wrong_preview_folder_types(tmp_path: Path, folder: str):
    catalog = catalog_fixture(tmp_path / "Wedding.lrcat")
    previews = preview_fixture(tmp_path, folder)
    assert probe_smart_previews(previews, catalog_path=catalog).readable is False


def test_rejects_missing_and_empty(tmp_path: Path):
    catalog = catalog_fixture(tmp_path / "Wedding.lrcat")
    assert not probe_smart_previews(tmp_path / "missing", catalog_path=catalog).readable
    empty = tmp_path / "Wedding Smart Previews.lrdata"
    empty.mkdir()
    assert not probe_smart_previews(empty, catalog_path=catalog).readable


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink privileges vary; Windows real fixture QA required")
def test_rejects_directory_symlinks(tmp_path: Path):
    catalog = catalog_fixture(tmp_path / "Wedding.lrcat")
    previews = preview_fixture(tmp_path)
    (previews / "linked").symlink_to(tmp_path, target_is_directory=True)
    assert not probe_smart_previews(previews, catalog_path=catalog).readable


def test_backend_selection_persists_but_remains_data_review(tmp_path: Path):
    store = PhotographerSetupStore(tmp_path / "setup.sqlite3")
    catalog = catalog_fixture(tmp_path / "Wedding.lrcat")
    previews = preview_fixture(tmp_path)
    with pytest.raises(ValueError, match="Catalog"):
        choose_smart_previews(str(previews), store=store)
    choose_catalog(str(catalog), store=store)
    overview = choose_smart_previews(str(previews), store=store)
    assert overview.setup.catalog_path == str(catalog.resolve())
    assert overview.setup.smart_previews_path == str(previews.resolve())
    assert overview.setup.status == "data_review"
    assert overview.selected_smart_previews.identity_verified is False
    assert any("עדיין לא אומתו" in text for text in overview.readiness_reasons)
    restarted = PhotographerSetupStore(tmp_path / "setup.sqlite3")
    assert restarted.get().smart_previews_path == str(previews.resolve())
    choose_catalog(str(catalog), store=store)
    assert store.get().smart_previews_path is None  # stale binding cleared


def test_existing_database_migrates_preview_column(tmp_path: Path):
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("""CREATE TABLE photographer_setup (
            singleton INTEGER PRIMARY KEY,
            source_type TEXT, catalog_path TEXT, edits_folder_path TEXT,
            style_name TEXT, preset_path TEXT, camera_profile TEXT,
            color_profile_mode TEXT, status TEXT, updated_at TEXT
        )""")
    store = PhotographerSetupStore(database)
    assert store.get().smart_previews_path is None
    assert store.get().source_type is None
