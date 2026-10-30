"""Event flow v1 (Lightroom catalog). Every catalog change is a planned job: dry run first, then explicit confirm.
See app.event_edit.service for the safety rules."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.event_edit import service
from app.event_edit.service import EventEditError

router = APIRouter(prefix="/api/event-edit", tags=["event-edit"])


class CatalogRequest(BaseModel):
    catalog_path: str = Field(min_length=1)


class ScopeRequest(CatalogRequest):
    folder_keys: list[str] = Field(min_length=1, max_length=200)


class AnchorPlanRequest(ScopeRequest):
    anchor_count: int | None = Field(default=None, ge=5, le=500)


class CompletionPlanRequest(ScopeRequest):
    fill_unanchored: bool = False
    automatic_exposure: bool = False


class AutomaticPlanRequest(ScopeRequest):
    profile_id: str = Field(min_length=1)
    relearn: bool = False


class UndoPlanRequest(BaseModel):
    job_id: str = Field(min_length=1)


class ConfirmRequest(BaseModel):
    confirm: Literal[True]
    # Dedicated confirmations a plan lists in `requires_acknowledgement` (e.g. a uniform exposure).
    acknowledge: list[Literal["uniform_exposure"]] = Field(default_factory=list, max_length=5)


def _call(fn, *args, **kwargs) -> dict:
    try:
        return fn(*args, **kwargs)
    except EventEditError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/folders")
def list_folders(payload: CatalogRequest) -> dict:
    """The catalog's folders with photos, to choose the event (read-only)."""
    return _call(service.folders, payload.catalog_path)


@router.post("/status")
def event_status(payload: ScopeRequest) -> dict:
    return _call(service.event_status, payload.catalog_path, payload.folder_keys)


@router.post("/plan/anchors")
def plan_anchors(payload: AnchorPlanRequest) -> dict:
    """Dry run: which photos would be marked for editing. Nothing is written."""
    return _call(service.plan_anchors, payload.catalog_path, payload.folder_keys, payload.anchor_count)


@router.post("/plan/complete")
def plan_completion(payload: CompletionPlanRequest) -> dict:
    """Dry run: what completing the event would write, skip and why. Nothing is written."""
    return _call(service.plan_completion, payload.catalog_path, payload.folder_keys,
                 fill_unanchored=payload.fill_unanchored, automatic_exposure=payload.automatic_exposure)


@router.post("/plan/auto")
def plan_automatic(payload: AutomaticPlanRequest) -> dict:
    """Dry run: edit the whole event automatically from a learning profile's style. Nothing is written."""
    return _call(service.plan_automatic, payload.catalog_path, payload.folder_keys, payload.profile_id,
                 relearn=payload.relearn)


@router.post("/plan/undo")
def plan_undo(payload: UndoPlanRequest) -> dict:
    """Dry run: which photos of a completion can be put back (only those untouched since). Nothing is written."""
    return _call(service.plan_undo, payload.job_id)


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    return _call(service.get_job, job_id)


@router.post("/jobs/{job_id}/confirm")
def confirm_job(job_id: str, payload: ConfirmRequest) -> dict:
    """Carry out a planned job after explicit confirmation; re-checked against the catalog before writing."""
    return _call(service.confirm, job_id, acknowledged=payload.acknowledge)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    return _call(service.cancel, job_id)
