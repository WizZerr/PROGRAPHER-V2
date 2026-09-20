from pathlib import Path

from app.photographer.edit_sources import probe_edits_folder
from app.photographer.setup_store import PhotographerSetupStore
from app.services.photographer_setup_service import (
    choose_edits_folder,
    continue_without_source,
)


def test_edits_folder_with_xmp_is_saved(tmp_path: Path) -> None:
    folder = tmp_path / "עריכות"
    folder.mkdir()
    (folder / "IMG_0001.xmp").write_text("<x:xmpmeta/>", encoding="utf-8")

    store = PhotographerSetupStore(tmp_path / "state.sqlite3")
    overview = choose_edits_folder(str(folder), store=store)

    assert overview.setup.source_type == "edits_folder"
    assert overview.setup.status == "data_review"
    assert overview.selected_edits_folder is not None
    assert overview.selected_edits_folder.xmp_files == 1


def test_empty_edits_folder_is_allowed_but_not_claimed_ready(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "empty"
    folder.mkdir()

    result = probe_edits_folder(folder)

    assert result.readable is True
    assert result.xmp_files == 0
    assert "עדיין אין" in result.note


def test_continue_without_existing_training_source(tmp_path: Path) -> None:
    store = PhotographerSetupStore(tmp_path / "state.sqlite3")
    overview = continue_without_source(store=store)

    assert overview.setup.source_type == "none"
    assert overview.setup.status == "needs_more_data"
    assert overview.setup.catalog_path is None
    assert overview.setup.edits_folder_path is None
