from fastapi import APIRouter, HTTPException, status

from app.schemas.photographer import (
    EditsFolderResponse,
    LightroomCatalogResponse,
    LightroomInstallationResponse,
    PhotographerSetupOverviewResponse,
    PhotographerSetupResponse,
    SelectCatalogRequest,
    SelectEditsFolderRequest,
)
from app.services.photographer_setup_service import (
    choose_catalog,
    choose_edits_folder,
    continue_without_source,
    get_setup_overview,
)

router = APIRouter(prefix="/api/photographer", tags=["photographer"])


def _response(overview) -> PhotographerSetupOverviewResponse:
    selected_catalog = overview.selected_catalog
    selected_edits_folder = overview.selected_edits_folder

    return PhotographerSetupOverviewResponse(
        lightroom=LightroomInstallationResponse(
            detected=overview.lightroom.detected,
            application_path=overview.lightroom.application_path,
            source=overview.lightroom.source,
        ),
        discovered_catalogs=overview.discovered_catalogs,
        setup=PhotographerSetupResponse(
            source_type=overview.setup.source_type,
            catalog_path=overview.setup.catalog_path,
            edits_folder_path=overview.setup.edits_folder_path,
            style_name=overview.setup.style_name,
            camera_profile=overview.setup.camera_profile,
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
