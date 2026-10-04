from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.rendering.jpeg_controls import (
    JPEG_CONTROL_CONTRACT_VERSION,
    JpegControlValidationError,
    JpegGlobalControls,
    jpeg_control_contract,
    jpeg_controls_to_recipe,
    validate_jpeg_controls,
)
from app.rendering.jpeg_product_render import (
    JpegProductRenderError,
    JpegRenderRevisionConflict,
    JpegRenderSourceUnavailable,
    JpegRenderStaleRevision,
    render_jpeg_product,
)
from app.rendering.jpeg_renderer import JpegRecipeValidationError


router = APIRouter(prefix="/api/jpeg-controls", tags=["jpeg-controls"])


class JpegControlsRequest(BaseModel):
    brightness: float = 0.0
    contrast: float = 0.0
    warmth: float = 0.0
    tint: float = 0.0


class JpegControlsPreviewRequest(BaseModel):
    event_id: str = Field(min_length=1)
    fingerprint: str = Field(min_length=1)
    revision: int = Field(ge=1)
    controls: JpegControlsRequest = Field(
        default_factory=JpegControlsRequest
    )


def _controls(payload: JpegControlsRequest) -> JpegGlobalControls:
    return validate_jpeg_controls(payload.model_dump())


@router.get("/contract")
def get_jpeg_control_contract() -> dict[str, Any]:
    return jpeg_control_contract()


@router.post("/recipe")
def build_jpeg_control_recipe(
    payload: JpegControlsRequest,
) -> dict[str, Any]:
    try:
        clean = _controls(payload)
        recipe = jpeg_controls_to_recipe(clean)
    except JpegControlValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return {
        "contract_version": JPEG_CONTROL_CONTRACT_VERSION,
        "controls": {
            "brightness": clean.brightness,
            "contrast": clean.contrast,
            "warmth": clean.warmth,
            "tint": clean.tint,
        },
        "recipe": recipe,
    }


@router.post("/preview")
def render_jpeg_controls_preview(
    payload: JpegControlsPreviewRequest,
) -> Response:
    try:
        clean = _controls(payload.controls)
        recipe = jpeg_controls_to_recipe(clean)
        artifact = render_jpeg_product(
            event_id=payload.event_id,
            fingerprint=payload.fingerprint,
            recipe=recipe,
            revision=payload.revision,
            mode="preview",
        )
    except JpegRenderSourceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        JpegRenderStaleRevision,
        JpegRenderRevisionConflict,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (
        JpegControlValidationError,
        JpegProductRenderError,
        JpegRecipeValidationError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return Response(
        content=artifact.payload,
        media_type=artifact.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-ProGrapher-JPEG-Control-Contract": (
                JPEG_CONTROL_CONTRACT_VERSION
            ),
            "X-ProGrapher-Recipe-Revision": str(artifact.revision),
            "X-ProGrapher-Recipe-SHA256": artifact.recipe_sha256,
            "X-ProGrapher-Render-Width": str(artifact.width),
            "X-ProGrapher-Render-Height": str(artifact.height),
        },
    )
