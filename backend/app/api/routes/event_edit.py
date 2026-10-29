"""Event flow v1: choose the anchors, complete the event, undo. Lightroom must be closed; see app.event_edit."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.event_edit import service
from app.event_edit.service import EventEditError

router = APIRouter(prefix="/api/event-edit", tags=["event-edit"])


class AnchorRequest(BaseModel):
    catalog_path: str = Field(min_length=1)
    anchor_count: int | None = Field(default=None, ge=5, le=500)


class CompleteRequest(BaseModel):
    catalog_path: str = Field(min_length=1)
    automatic_exposure: bool = True


class UndoRequest(BaseModel):
    catalog_path: str = Field(min_length=1)
    backup: str = Field(min_length=1)


@router.post("/anchors")
def choose_anchors(payload: AnchorRequest) -> dict:
    """Mark the photos the photographer edits (collection + purple label). Backs the catalog up first."""
    try:
        return service.plan_anchors(payload.catalog_path, payload.anchor_count)
    except EventEditError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/complete")
def complete_event(payload: CompleteRequest) -> dict:
    """Write every photo the photographer did not edit, from the edited anchors. Backs the catalog up first."""
    try:
        return service.complete(payload.catalog_path, automatic_exposure=payload.automatic_exposure)
    except EventEditError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/undo")
def undo_event(payload: UndoRequest) -> dict:
    """Put the catalog back exactly as it was before the step that made this backup."""
    try:
        return service.undo(payload.catalog_path, payload.backup)
    except EventEditError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
