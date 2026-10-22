"""Local profile onboarding; strictly preparatory, never a training endpoint."""
from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.learning_intake.service import LearningIntakeError, LearningProfileStore
from app.learning_intake.discovery import discover_catalogs

router = APIRouter(prefix="/api/learning-intake", tags=["learning-intake"])


class DiscoverCatalogLocation(BaseModel):
    path: str = Field(min_length=1)


@router.post("/discover")
def discover_catalog_location(payload: DiscoverCatalogLocation) -> dict:
    try:
        return discover_catalogs(payload.path)
    except LearningIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class CreateLearningProfile(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    photography_type: str = Field(min_length=1, max_length=80)
    color_mode: Literal["color", "black_white"] = "color"
    consent: bool


class AttachLearningCatalog(BaseModel):
    catalog_path: str = Field(min_length=1)
    smart_previews_path: str | None = None
    raw_fallback_path: str | None = None


class SamplePreflightRequest(BaseModel):
    catalog_path: str = Field(min_length=1)
    raw_folder: str | None = None
    sample_size: int = Field(default=16, ge=1, le=16)


@router.get("/profiles")
def list_profiles() -> dict:
    return {"profiles": LearningProfileStore().list()}


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: str) -> dict:
    try:
        return LearningProfileStore().get(profile_id)
    except LearningIntakeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/profiles", status_code=201)
def create_profile(payload: CreateLearningProfile) -> dict:
    try:
        return LearningProfileStore().create(**payload.model_dump())
    except LearningIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/profiles/{profile_id}/sample-preflight")
def sample_preflight(profile_id: str, payload: SamplePreflightRequest) -> dict:
    """Transient private per-photo review. Not a dataset certification."""
    try:
        return LearningProfileStore().preview_sample(
            profile_id, **payload.model_dump()
        )
    except LearningIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: str) -> dict:
    try:
        LearningProfileStore().delete(profile_id)
    except LearningIntakeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # apiRequest expects a JSON response. Do not return 204 No Content here.
    return {"deleted": True}


@router.post("/profiles/{profile_id}/catalogs")
def attach_catalog(profile_id: str, payload: AttachLearningCatalog) -> dict:
    try:
        return LearningProfileStore().attach_catalog(profile_id, **payload.model_dump())
    except LearningIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
