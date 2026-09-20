from pydantic import BaseModel, Field


class MetadataReadRequest(BaseModel):
    path: str = Field(min_length=1)


class PhotoMetadata(BaseModel):
    path: str
    status: str
    make: str | None = None
    model: str | None = None
    date_time_original: str | None = None
    exposure_time: str | None = None
    f_number: str | None = None
    iso: str | None = None
    focal_length: str | None = None
