from typing import Literal

from fastapi import APIRouter, HTTPException, status

from app.schemas.testing import (
    ExportRecipesRequest,
    ExportRecipesResponse,
    ReviewSheet,
    TestingProfileRequest,
    TestingProfileSummary,
)
from app.testing.profile import (
    active_testing_profile,
    build_review_sheet,
    build_testing_profile,
    export_testing_recipes,
)

router = APIRouter(prefix="/api/testing", tags=["testing"])


@router.get("/profile", response_model=TestingProfileSummary)
def get_profile(
    learning_source: Literal["raw", "jpeg"] | None = None,
) -> TestingProfileSummary:
    profile = active_testing_profile(learning_source)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="עדיין אין פרופיל בדיקה. יש לבנות אותו מתיקיית RAW או JPEG.",
        )
    return profile


@router.post("/profile", response_model=TestingProfileSummary)
def create_profile(payload: TestingProfileRequest) -> TestingProfileSummary:
    try:
        return build_testing_profile(
            raw_root=payload.raw_root,
            edits_root=payload.edits_root,
            photographer_id=payload.photographer_id.strip() or "local-photographer",
            event_label=payload.event_label.strip() or "reference",
            learning_source=payload.learning_source,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get("/events/{event_id}/review", response_model=ReviewSheet)
def review(event_id: str) -> ReviewSheet:
    try:
        return build_review_sheet(event_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/export", response_model=ExportRecipesResponse)
def export_recipes(payload: ExportRecipesRequest) -> ExportRecipesResponse:
    try:
        return export_testing_recipes(
            event_id=payload.event_id,
            output_dir=payload.output_dir,
            items=payload.items,
        )
    except ValueError as exc:
        detail = str(exc)
        missing = detail == "האירוע לא נמצא."
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if missing
                else status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=detail,
        ) from exc
