from typing import Literal

from pydantic import BaseModel, Field


class EventOpenRequest(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = None


class EventRelinkRequest(BaseModel):
    path: str = Field(min_length=1)


class EventSummary(BaseModel):
    id: str
    name: str
    root_path: str
    total_files: int
    raw_files: int
    rendered_files: int
    created_at: str
    updated_at: str


class EventOpenResponse(BaseModel):
    event: EventSummary
    result: Literal["created", "existing", "updated"]
    duplicate_files_ignored: int
    new_files_added: int


class EventListResponse(BaseModel):
    events: list[EventSummary]


class EventAvailabilityResponse(BaseModel):
    event_id: str
    root_exists: bool
    tracked_files: int
    available_files: int
    missing_files: int


class EventRelinkResponse(BaseModel):
    event: EventSummary
    matched_files: int
    missing_files: int
    new_files_added: int
