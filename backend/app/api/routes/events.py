from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.schemas.events import (
    EventAvailabilityResponse,
    EventDeleteResponse,
    EventFileListResponse,
    EventFileRecord,
    EventListResponse,
    EventOpenRequest,
    EventOpenResponse,
    EventRelinkRequest,
    EventRelinkResponse,
    EventScanStartResponse,
    EventScanStatusResponse,
    EventSummary,
)
from app.preview.embedded_jpeg import PreviewUnavailable, camera_preview_bytes
from app.testing.profile import forget_event_reviews
from app.services.event_scan_jobs import get_scan_job, start_scan_job
from app.services.event_service import (
    EventOpenError,
    delete_event,
    event_availability,
    list_event_files,
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
        jpeg_files=record.jpeg_files,
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


@router.delete("/{event_id}", response_model=EventDeleteResponse)
def remove_event(event_id: str) -> EventDeleteResponse:
    try:
        event = delete_event(event_id)
    except EventOpenError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    forget_event_reviews(event_id)
    return EventDeleteResponse(
        event_id=event.id,
        name=event.name,
        removed_from_catalog=True,
        source_files_deleted=False,
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
    "/{event_id}/files",
    response_model=EventFileListResponse,
)
def files(event_id: str, limit: int | None = None) -> EventFileListResponse:
    try:
        records = list_event_files(event_id, limit=limit)
    except EventOpenError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return EventFileListResponse(
        event_id=event_id,
        files=[
            EventFileRecord(
                fingerprint=item.fingerprint,
                absolute_path=item.absolute_path,
                relative_path=item.relative_path,
                filename=item.filename,
                extension=item.extension,
                source_type=item.source_type,
                size_bytes=item.size_bytes,
                present=item.present,
            )
            for item in records
        ],
    )


@router.get("/{event_id}/files/{fingerprint}/preview")
def file_preview(event_id: str, fingerprint: str) -> Response:
    try:
        payload = camera_preview_bytes(event_id, fingerprint)
    except PreviewUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(
        content=payload,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=3600"},
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
