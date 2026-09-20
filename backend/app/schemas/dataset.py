from pydantic import BaseModel, Field


class DatasetPreviewRequest(BaseModel):
    raw_root: str = Field(min_length=1)
    edits_root: str = Field(min_length=1)
    event_id: str = Field(min_length=1)


class DatasetPreviewResponse(BaseModel):
    event_id: str
    raw_files: int
    xmp_files: int
    matched_pairs: int
    unmatched_raw: int
    ambiguous_raw: int
    verified_training_pairs: int
    note: str
