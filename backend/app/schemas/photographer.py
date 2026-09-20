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


class LightroomPresetResponse(BaseModel):
    path: str
    name: str


class PhotographerSetupResponse(BaseModel):
    source_type: Literal[
        "lightroom_catalog",
        "edits_folder",
        "none",
    ] | None
    catalog_path: str | None
    edits_folder_path: str | None
    style_name: str | None
    preset_path: str | None
    camera_profile: str | None
    color_profile_mode: Literal["from_source", "explicit"]
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
    discovered_presets: list[LightroomPresetResponse]
    setup: PhotographerSetupResponse
    selected_catalog: LightroomCatalogResponse | None
    selected_edits_folder: EditsFolderResponse | None
    readiness_reasons: list[str]


class SelectCatalogRequest(BaseModel):
    path: str = Field(min_length=1)


class SelectEditsFolderRequest(BaseModel):
    path: str = Field(min_length=1)


class StylePreferencesRequest(BaseModel):
    style_name: str | None = None
    preset_path: str | None = None
    color_profile_mode: Literal["from_source", "explicit"] = "from_source"
    camera_profile: str | None = None
