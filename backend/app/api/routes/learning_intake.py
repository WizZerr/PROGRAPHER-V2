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


class SmartPreviewProbeRequest(BaseModel):
    catalog_path: str = Field(min_length=1)


class SmartPreviewSdkReviewRequest(BaseModel):
    catalog_path: str = Field(min_length=1)
    evidence_path: str = Field(min_length=1)


class SmartPreviewLinkRequest(BaseModel):
    catalog_path: str = Field(min_length=1)
    sample_size: int = Field(default=4, ge=0, le=4)


class AnchorBacktestRequest(BaseModel):
    catalog_path: str = Field(min_length=1)
    anchors: int = Field(default=100, ge=5, le=500)
    sample_size: int = Field(default=4, ge=0, le=4)


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


@router.post("/profiles/{profile_id}/smart-preview-sdk-review")
def review_smart_preview_sdk_links(profile_id: str, payload: SmartPreviewSdkReviewRequest) -> dict:
    """Corroborate local SDK link evidence; never certify learning samples."""
    try:
        return LearningProfileStore().review_smart_preview_sdk_links(
            profile_id, **payload.model_dump()
        )
    except LearningIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/profiles/{profile_id}/smart-preview-probe")
def probe_smart_preview_contents(profile_id: str, payload: SmartPreviewProbeRequest) -> dict:
    """Local authenticated DNG inventory/decode; does not certify Lightroom IDs."""
    try:
        return LearningProfileStore().probe_smart_previews(
            profile_id, catalog_path=payload.catalog_path,
        )
    except LearningIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/profiles/{profile_id}/smart-preview-links")
def link_smart_previews(profile_id: str, payload: SmartPreviewLinkRequest) -> dict:
    """Stage 3: catalog photo -> Smart Preview DNG links; local, transient, not training-ready."""
    try:
        return LearningProfileStore().link_smart_previews(profile_id, **payload.model_dump())
    except LearningIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/profiles/{profile_id}/edit-pairs")
def build_edit_pairs(profile_id: str, payload: SmartPreviewLinkRequest) -> dict:
    """Stage 4: before/after pairs for review; local, transient, not training-ready."""
    try:
        return LearningProfileStore().edit_pairs(profile_id, **payload.model_dump())
    except LearningIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/profiles/{profile_id}/anchor-backtest")
def run_anchor_backtest(profile_id: str, payload: AnchorBacktestRequest) -> dict:
    """Stage 5: measure the anchor style method on this catalog; nothing stored or applied."""
    try:
        return LearningProfileStore().anchor_backtest(profile_id, **payload.model_dump())
    except LearningIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/profiles/{profile_id}/analyze")
def analyze_catalog(profile_id: str, payload: SmartPreviewProbeRequest) -> dict:
    """Photographer flow: one call from a linked catalog to its style summary and expected savings."""
    try:
        return LearningProfileStore().analyze_catalog(profile_id, catalog_path=payload.catalog_path)
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
