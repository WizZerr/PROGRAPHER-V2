from typing import Literal

from pydantic import BaseModel, Field


class DatasetPreviewRequest(BaseModel):
    raw_root: str = Field(min_length=1)
    edits_root: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    photographer_id: str | None = None
    lightroom_version: str | None = None
    style_label: str | None = None


class DatasetPreviewResponse(BaseModel):
    event_id: str
    raw_files: int
    xmp_files: int
    matched_pairs: int
    unmatched_raw: int
    ambiguous_raw: int
    verified_training_pairs: int
    note: str


class DatasetReviewDecision(BaseModel):
    fingerprint: str = Field(min_length=1)
    decision: Literal["verified_final", "rejected"]


class DatasetRightsRequest(BaseModel):
    permission_basis: Literal[
        "unspecified",
        "photographer_owned",
        "client_permission",
        "licensed_dataset",
        "other",
    ] = "unspecified"
    allow_personal_training: bool = False
    allow_general_training: bool = False
    license_name: str | None = None
    notes: str | None = None


class DatasetManifestRequest(DatasetPreviewRequest):
    decisions: list[DatasetReviewDecision] = Field(default_factory=list)
    rights: DatasetRightsRequest = Field(
        default_factory=DatasetRightsRequest
    )


class DatasetManifestResponse(BaseModel):
    manifest_id: str
    manifest_path: str
    event_id: str
    raw_files: int
    matched_pairs: int
    verified_training_pairs: int
    usable_personal_training_pairs: int
    excluded_pairs: int
    readiness_state: str
    readiness_reasons: list[str]
    note: str
