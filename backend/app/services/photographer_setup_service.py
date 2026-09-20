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
from app.photographer.presets import (
    LightroomPreset,
    discover_lightroom_presets,
    validate_preset,
)
from app.photographer.setup_store import (
    PhotographerSetup,
    PhotographerSetupStore,
)


@dataclass(frozen=True)
class PhotographerSetupOverview:
    lightroom: LightroomInstallation
    discovered_catalogs: list[str]
    discovered_presets: list[LightroomPreset]
    setup: PhotographerSetup
    selected_catalog: LightroomCatalogProbe | None
    selected_edits_folder: EditsFolderProbe | None
    readiness_reasons: list[str]


def _readiness_reasons(setup: PhotographerSetup) -> list[str]:
    reasons: list[str] = []

    if setup.source_type in (None, "none"):
        reasons.append("אין כרגע מקור לעריכות אישיות.")

    # Phase 7 must not claim readiness before Phase 8 proves valid pairs.
    reasons.append(
        "טרם נבדקו זוגות RAW ↔ עריכה סופית תקינים לפי זהות מקור."
    )

    if (
        setup.color_profile_mode == "explicit"
        and not setup.camera_profile
    ):
        reasons.append("נבחר פרופיל צבע מפורש אך לא הוזן שם פרופיל.")

    return reasons


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
        discovered_presets=discover_lightroom_presets(),
        setup=setup,
        selected_catalog=selected_catalog,
        selected_edits_folder=selected_edits_folder,
        readiness_reasons=_readiness_reasons(setup),
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


def save_style_preferences(
    *,
    style_name: str | None,
    preset_path: str | None,
    color_profile_mode: str,
    camera_profile: str | None,
    store: PhotographerSetupStore | None = None,
) -> PhotographerSetupOverview:
    if color_profile_mode not in {"from_source", "explicit"}:
        raise ValueError("מצב פרופיל הצבע אינו נתמך.")

    normalized_style = style_name.strip() if style_name else None
    normalized_profile = camera_profile.strip() if camera_profile else None

    normalized_preset: str | None = None
    if preset_path:
        normalized_preset = validate_preset(preset_path).path

    if color_profile_mode == "explicit" and not normalized_profile:
        raise ValueError("יש להזין שם פרופיל צבע מפורש.")

    setup_store = store or PhotographerSetupStore()
    setup_store.save_style_preferences(
        style_name=normalized_style,
        preset_path=normalized_preset,
        color_profile_mode=color_profile_mode,
        camera_profile=(
            normalized_profile
            if color_profile_mode == "explicit"
            else None
        ),
    )

    return get_setup_overview(setup_store)
