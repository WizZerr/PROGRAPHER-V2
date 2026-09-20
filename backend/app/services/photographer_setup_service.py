from __future__ import annotations

from dataclasses import dataclass

from app.photographer.edit_sources import (
    EditsFolderProbe,
    probe_edits_folder,
)
from app.photographer.lightroom import (
    LightroomCatalogProbe,
    LightroomInstallation,
    detect_lightroom,
    discover_default_catalogs,
    probe_catalog,
)
from app.photographer.setup_store import (
    PhotographerSetup,
    PhotographerSetupStore,
)


@dataclass(frozen=True)
class PhotographerSetupOverview:
    lightroom: LightroomInstallation
    discovered_catalogs: list[str]
    setup: PhotographerSetup
    selected_catalog: LightroomCatalogProbe | None
    selected_edits_folder: EditsFolderProbe | None


def get_setup_overview(
    store: PhotographerSetupStore | None = None,
) -> PhotographerSetupOverview:
    setup_store = store or PhotographerSetupStore()
    setup = setup_store.get()

    selected_catalog = (
        probe_catalog(setup.catalog_path)
        if setup.catalog_path
        else None
    )
    selected_edits_folder = (
        probe_edits_folder(setup.edits_folder_path)
        if setup.edits_folder_path
        else None
    )

    return PhotographerSetupOverview(
        lightroom=detect_lightroom(),
        discovered_catalogs=discover_default_catalogs(),
        setup=setup,
        selected_catalog=selected_catalog,
        selected_edits_folder=selected_edits_folder,
    )


def choose_catalog(
    catalog_path: str,
    store: PhotographerSetupStore | None = None,
) -> PhotographerSetupOverview:
    probe = probe_catalog(catalog_path)

    if not probe.exists or not probe.readable or not probe.sqlite_valid:
        raise ValueError(probe.note)

    setup_store = store or PhotographerSetupStore()
    setup_store.save_catalog(probe.path)
    return get_setup_overview(setup_store)


def choose_edits_folder(
    folder_path: str,
    store: PhotographerSetupStore | None = None,
) -> PhotographerSetupOverview:
    probe = probe_edits_folder(folder_path)

    if not probe.exists or not probe.readable:
        raise ValueError(probe.note)

    setup_store = store or PhotographerSetupStore()
    setup_store.save_edits_folder(probe.path)
    return get_setup_overview(setup_store)


def continue_without_source(
    store: PhotographerSetupStore | None = None,
) -> PhotographerSetupOverview:
    setup_store = store or PhotographerSetupStore()
    setup_store.save_no_source()
    return get_setup_overview(setup_store)
