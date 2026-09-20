from typing import Literal

from pydantic import BaseModel, Field


class LightroomInstallationResponse(BaseModel):
    detected: bool
    application_path: str | None
    source: str | None


class LightroomCatalogResponse(BaseModel):
    path: str
    exists: bool
    readable: bool
    sqlite_valid: bool
    catalog_photo_records: int | None
    note: str


class EditsFolderResponse(BaseModel):
    path: str
    exists: bool
    readable: bool
    xmp_files: int
    note: str


class PhotographerSetupResponse(BaseModel):
    source_type: Literal[
        "lightroom_catalog",
        "edits_folder",
        "none",
    ] | None
    catalog_path: str | None
    edits_folder_path: str | None
    style_name: str | None
    camera_profile: str | None
    status: Literal[
        "no_profile",
        "data_review",
        "training",
        "needs_more_data",
        "experimental",
        "evaluated",
    ]
    updated_at: str | None


class PhotographerSetupOverviewResponse(BaseModel):
    lightroom: LightroomInstallationResponse
    discovered_catalogs: list[str]
    setup: PhotographerSetupResponse
    selected_catalog: LightroomCatalogResponse | None
    selected_edits_folder: EditsFolderResponse | None


class SelectCatalogRequest(BaseModel):
    path: str = Field(min_length=1)


class SelectEditsFolderRequest(BaseModel):
    path: str = Field(min_length=1)
