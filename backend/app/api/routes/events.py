from fastapi import APIRouter, HTTPException, status

from app.schemas.events import (
    EventAvailabilityResponse,
    EventListResponse,
    EventOpenRequest,
    EventOpenResponse,
    EventRelinkRequest,
    EventRelinkResponse,
    EventSummary,
)
from app.services.event_service import (
    EventOpenError,
    event_availability,
    list_events,
    open_event_folder,
    relink_event,
)

router = APIRouter(prefix="/api/events", tags=["events"])


def _summary(record) -> EventSummary:
    return EventSummary(
        id=record.id,
        name=record.name,
        root_path=record.root_path,
        total_files=record.total_files,
        raw_files=record.raw_files,
        rendered_files=record.rendered_files,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("", response_model=EventListResponse)
def get_events() -> EventListResponse:
    return EventListResponse(
        events=[_summary(record) for record in list_events()]
    )


@router.post("/open-folder", response_model=EventOpenResponse)
def open_folder(payload: EventOpenRequest) -> EventOpenResponse:
    try:
        result = open_event_folder(
            path=payload.path,
            name=payload.name,
        )
    except EventOpenError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return EventOpenResponse(
        event=_summary(result.event),
        result=result.result,
        duplicate_files_ignored=result.duplicate_files_ignored,
        new_files_added=result.new_files_added,
    )


@router.get(
    "/{event_id}/availability",
    response_model=EventAvailabilityResponse,
)
def availability(event_id: str) -> EventAvailabilityResponse:
    try:
        result = event_availability(event_id)
    except EventOpenError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return EventAvailabilityResponse(
        event_id=result.event_id,
        root_exists=result.root_exists,
        tracked_files=result.tracked_files,
        available_files=result.available_files,
        missing_files=result.missing_files,
    )


@router.post(
    "/{event_id}/relink",
    response_model=EventRelinkResponse,
)
def relink(event_id: str, payload: EventRelinkRequest) -> EventRelinkResponse:
    try:
        result = relink_event(event_id, payload.path)
    except EventOpenError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return EventRelinkResponse(
        event=_summary(result.event),
        matched_files=result.matched_files,
        missing_files=result.missing_files,
        new_files_added=result.new_files_added,
    )
