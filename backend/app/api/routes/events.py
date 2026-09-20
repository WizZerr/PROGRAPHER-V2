from fastapi import APIRouter, HTTPException, status

from app.schemas.events import (
    EventAvailabilityResponse,
    EventListResponse,
    EventOpenRequest,
    EventOpenResponse,
    EventRelinkRequest,
    EventRelinkResponse,
    EventScanStartResponse,
    EventScanStatusResponse,
    EventSummary,
)
from app.services.event_scan_jobs import get_scan_job, start_scan_job
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


def _open_response(result) -> EventOpenResponse:
    return EventOpenResponse(
        event=_summary(result.event),
        result=result.result,
        duplicate_files_ignored=result.duplicate_files_ignored,
        new_files_added=result.new_files_added,
    )


@router.get("", response_model=EventListResponse)
def get_events() -> EventListResponse:
    return EventListResponse(
        events=[_summary(record) for record in list_events()]
    )


@router.post("/open-folder", response_model=EventOpenResponse)
def open_folder(payload: EventOpenRequest) -> EventOpenResponse:
    # Retained as a synchronous compatibility route.
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

    return _open_response(result)


@router.post("/scan", response_model=EventScanStartResponse)
def scan_folder(payload: EventOpenRequest) -> EventScanStartResponse:
    try:
        job = start_scan_job(payload.path, payload.name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return EventScanStartResponse(
        job_id=job.id,
        status=job.status,
    )


@router.get(
    "/scan/{job_id}",
    response_model=EventScanStatusResponse,
)
def scan_status(job_id: str) -> EventScanStatusResponse:
    job = get_scan_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="משימת הסריקה לא נמצאה.",
        )

    percent = (
        round((job.processed_files / job.total_files) * 100)
        if job.total_files > 0
        else 0
    )

    return EventScanStatusResponse(
        job_id=job.id,
        status=job.status,
        processed_files=job.processed_files,
        total_files=job.total_files,
        current_file=job.current_file,
        percent=max(0, min(100, percent)),
        error=job.error,
        result=_open_response(job.result) if job.result else None,
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
