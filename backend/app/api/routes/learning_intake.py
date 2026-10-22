"""Local profile onboarding; strictly preparatory, never a training endpoint."""
from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.learning_intake.service import LearningIntakeError, LearningProfileStore

router = APIRouter(prefix="/api/learning-intake", tags=["learning-intake"])


class CreateLearningProfile(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    photography_type: str = Field(min_length=1, max_length=80)
    color_mode: Literal["color", "black_white"] = "color"
    consent: bool


class AttachLearningCatalog(BaseModel):
    catalog_path: str = Field(min_length=1)
    smart_previews_path: str | None = None
    raw_fallback_path: str | None = None


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


@router.post("/profiles/{profile_id}/catalogs")
def attach_catalog(profile_id: str, payload: AttachLearningCatalog) -> dict:
    try:
        return LearningProfileStore().attach_catalog(profile_id, **payload.model_dump())
    except LearningIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
