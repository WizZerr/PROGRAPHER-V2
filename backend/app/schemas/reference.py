from pydantic import BaseModel, Field


class RecipePayload(BaseModel):
    exposure: float | None = None
    temperature: int | None = None
    tint: int | None = None
    blacks: float | None = None
    process_version: str | None = None
    camera_profile: str | None = None


class RoundTripRequest(BaseModel):
    raw_path: str = Field(min_length=1)
    output_dir: str = Field(min_length=1)
    recipe: RecipePayload


class RoundTripResponse(BaseModel):
    source_fingerprint: str
    written_xmp_path: str
    source_unchanged: bool
    recipe_matches: bool
    mismatches: list[str]
    note: str


class RegisterReferenceRequest(BaseModel):
    raw_path: str = Field(min_length=1)
    render_path: str = Field(min_length=1)
    color_space: str = Field(min_length=1)
    file_format: str = Field(min_length=1)
    process_family: str = Field(min_length=1)
    lightroom_version: str | None = None
    recipe: RecipePayload


class RegisterReferenceResponse(BaseModel):
    case_id: str
    manifest_path: str
    render_sha256: str
    status: str
    note: str
