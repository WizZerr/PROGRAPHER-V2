from fastapi import APIRouter, HTTPException, status

from app.schemas.photographer import (
    EditsFolderResponse,
    LightroomCatalogResponse,
    LightroomInstallationResponse,
    LightroomPresetResponse,
    PhotographerSetupOverviewResponse,
    PhotographerSetupResponse,
    SelectCatalogRequest,
    SelectSmartPreviewsRequest,
    SmartPreviewsResponse,
    SelectEditsFolderRequest,
    StylePreferencesRequest,
)
from app.services.photographer_setup_service import (
    choose_catalog,
    choose_smart_previews,
    choose_edits_folder,
    continue_without_source,
    get_setup_overview,
    save_style_preferences,
)

router = APIRouter(prefix="/api/photographer", tags=["photographer"])


def _response(overview) -> PhotographerSetupOverviewResponse:
    selected_catalog = overview.selected_catalog
    selected_edits_folder = overview.selected_edits_folder
    selected_smart_previews = overview.selected_smart_previews

    return PhotographerSetupOverviewResponse(
        lightroom=LightroomInstallationResponse(
            detected=overview.lightroom.detected,
            application_path=overview.lightroom.application_path,
            source=overview.lightroom.source,
        ),
        discovered_catalogs=overview.discovered_catalogs,
        discovered_presets=[
            LightroomPresetResponse(
                path=preset.path,
                name=preset.name,
            )
            for preset in overview.discovered_presets
        ],
        setup=PhotographerSetupResponse(
            source_type=overview.setup.source_type,
            catalog_path=overview.setup.catalog_path,
            smart_previews_path=overview.setup.smart_previews_path,
            edits_folder_path=overview.setup.edits_folder_path,
            style_name=overview.setup.style_name,
            preset_path=overview.setup.preset_path,
            camera_profile=overview.setup.camera_profile,
            color_profile_mode=overview.setup.color_profile_mode,
            status=overview.setup.status,
            updated_at=overview.setup.updated_at,
        ),
        selected_catalog=(
            LightroomCatalogResponse(
                path=selected_catalog.path,
                exists=selected_catalog.exists,
                readable=selected_catalog.readable,
                sqlite_valid=selected_catalog.sqlite_valid,
                catalog_photo_records=selected_catalog.catalog_photo_records,
                note=selected_catalog.note,
            )
            if selected_catalog
            else None
        ),
        selected_smart_previews=(
            SmartPreviewsResponse(
                path=selected_smart_previews.path,
                exists=selected_smart_previews.exists,
                readable=selected_smart_previews.readable,
                asset_files=selected_smart_previews.asset_files,
                total_bytes=selected_smart_previews.total_bytes,
                name_matches_catalog=selected_smart_previews.name_matches_catalog,
                identity_verified=selected_smart_previews.identity_verified,
                note=selected_smart_previews.note,
            ) if selected_smart_previews else None
        ),
        selected_edits_folder=(
            EditsFolderResponse(
                path=selected_edits_folder.path,
                exists=selected_edits_folder.exists,
                readable=selected_edits_folder.readable,
                xmp_files=selected_edits_folder.xmp_files,
                note=selected_edits_folder.note,
            )
            if selected_edits_folder
            else None
        ),
        readiness_reasons=overview.readiness_reasons,
    )


@router.get("/setup", response_model=PhotographerSetupOverviewResponse)
def setup_overview() -> PhotographerSetupOverviewResponse:
    return _response(get_setup_overview())


@router.post(
    "/setup/catalog",
    response_model=PhotographerSetupOverviewResponse,
)
def select_catalog(
    payload: SelectCatalogRequest,
) -> PhotographerSetupOverviewResponse:
    try:
        return _response(choose_catalog(payload.path))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.post(
    "/setup/smart-previews",
    response_model=PhotographerSetupOverviewResponse,
)
def select_smart_previews(
    payload: SelectSmartPreviewsRequest,
) -> PhotographerSetupOverviewResponse:
    try:
        return _response(choose_smart_previews(payload.path))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.post(
    "/setup/edits-folder",
    response_model=PhotographerSetupOverviewResponse,
)
def select_edits_folder(
    payload: SelectEditsFolderRequest,
) -> PhotographerSetupOverviewResponse:
    try:
        return _response(choose_edits_folder(payload.path))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.post(
    "/setup/no-source",
    response_model=PhotographerSetupOverviewResponse,
)
def no_source() -> PhotographerSetupOverviewResponse:
    return _response(continue_without_source())


@router.post(
    "/setup/style",
    response_model=PhotographerSetupOverviewResponse,
)
def style_preferences(
    payload: StylePreferencesRequest,
) -> PhotographerSetupOverviewResponse:
    try:
        return _response(
            save_style_preferences(
                style_name=payload.style_name,
                preset_path=payload.preset_path,
                color_profile_mode=payload.color_profile_mode,
                camera_profile=payload.camera_profile,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
