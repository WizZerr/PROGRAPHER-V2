from typing import Literal

from pydantic import BaseModel, Field


class TestingProfileRequest(BaseModel):
    raw_root: str = Field(min_length=1)
    edits_root: str = Field(min_length=1)
    photographer_id: str = "local-photographer"
    event_label: str = "reference"
    learning_source: Literal["raw", "jpeg"] = "raw"


class ActivateTestingProfileRequest(BaseModel):
    learning_source: Literal["raw", "jpeg"]


class RecipeValues(BaseModel):
    exposure: float | None = None
    temperature: int | None = None
    tint: int | None = None
    process_version: str | None = None
    camera_profile: str | None = None


class BaselineValues(BaseModel):
    exposure: float
    temperature: int
    tint: int
    sample_count: int
    strategy: Literal["median"] = "median"


class TestingProfileSummary(BaseModel):
    profile_id: str
    created_at: str
    photographer_id: str
    learning_source: Literal["raw", "jpeg"] = "raw"
    learning_material: Literal["raw_xmp", "jpeg_pairs"]
    dataset_manifest_path: str | None = None
    raw_root: str
    edits_root: str
    event_label: str
    raw_files: int
    xmp_files: int
    matched_pairs: int
    ambiguous_raw: int
    unmatched_raw: int
    usable_pairs: int
    excluded_local_adjustments: int
    excluded_missing_targets: int
    baseline: BaselineValues | None
    quality_claim_allowed: bool = False
    warnings: list[str]
    note: str


class ReviewFile(BaseModel):
    fingerprint: str
    filename: str
    relative_path: str
    absolute_path: str
    pair_status: str
    photographer: RecipeValues | None
    baseline: RecipeValues | None
    saved_review: RecipeValues | None
    suggested: RecipeValues | None
    exclusion_reasons: list[str]


class ReviewSheet(BaseModel):
    event_id: str
    event_name: str
    learning_source: Literal["raw", "jpeg"] = "raw"
    quality_claim_allowed: bool = False
    baseline: BaselineValues | None
    files: list[ReviewFile]
    note: str


class ExportRecipeItem(BaseModel):
    fingerprint: str = Field(min_length=1)
    exposure: float = Field(ge=-5.0, le=5.0)
    temperature: int = Field(ge=2000, le=50000)
    tint: int = Field(ge=-150, le=150)
    decision: Literal["approved", "corrected"] = "corrected"


class SaveReviewRequest(BaseModel):
    event_id: str = Field(min_length=1)
    item: ExportRecipeItem


class SaveReviewResponse(BaseModel):
    event_id: str
    fingerprint: str
    decision: Literal["approved", "corrected"]
    recipe: RecipeValues
    saved_at: str


class ExportRecipesRequest(BaseModel):
    event_id: str = Field(min_length=1)
    output_dir: str = Field(min_length=1)
    items: list[ExportRecipeItem] = Field(min_length=1)


class ExportFileResult(BaseModel):
    fingerprint: str
    status: Literal["written", "skipped"]
    path: str | None
    reason: str | None
    source_unchanged: bool


class ExportRecipesResponse(BaseModel):
    event_id: str
    output_dir: str
    written: int
    skipped: int
    files: list[ExportFileResult]
    note: str
