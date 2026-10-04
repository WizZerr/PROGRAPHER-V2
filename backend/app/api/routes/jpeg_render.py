from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.rendering.jpeg_product_render import (
    JpegProductRenderError,
    JpegRenderRevisionConflict,
    JpegRenderSourceUnavailable,
    JpegRenderStaleRevision,
    assert_current_jpeg_revision,
    render_jpeg_product,
)
from app.rendering.jpeg_renderer import JpegRecipeValidationError


router = APIRouter(prefix="/api/events", tags=["jpeg-render"])


class JpegProductRenderRequest(BaseModel):
    revision: int = Field(ge=1)
    recipe: dict[str, Any]


def _raise_render_http(exc: Exception) -> None:
    if isinstance(exc, JpegRenderSourceUnavailable):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, (JpegRenderStaleRevision, JpegRenderRevisionConflict)):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_422_UNPROCESSABLE_CONTENT

    raise HTTPException(status_code=code, detail=str(exc)) from exc


def _render_response(
    event_id: str,
    fingerprint: str,
    payload: JpegProductRenderRequest,
    mode: str,
) -> Response:
    try:
        artifact = render_jpeg_product(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=payload.recipe,
            revision=payload.revision,
            mode=mode,
        )
    except (
        JpegProductRenderError,
        JpegRecipeValidationError,
    ) as exc:
        _raise_render_http(exc)

    return Response(
        content=artifact.payload,
        media_type=artifact.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-ProGrapher-Render-Mode": artifact.mode,
            "X-ProGrapher-Recipe-Revision": str(artifact.revision),
            "X-ProGrapher-Recipe-SHA256": artifact.recipe_sha256,
            "X-ProGrapher-Source-SHA256": artifact.source_sha256,
            "X-ProGrapher-Render-Width": str(artifact.width),
            "X-ProGrapher-Render-Height": str(artifact.height),
            "X-ProGrapher-Render-Cache": (
                "hit" if artifact.cache_hit else "miss"
            ),
        },
    )


@router.post("/{event_id}/files/{fingerprint}/jpeg-render/preview")
def jpeg_render_preview(
    event_id: str,
    fingerprint: str,
    payload: JpegProductRenderRequest,
) -> Response:
    return _render_response(
        event_id,
        fingerprint,
        payload,
        "preview",
    )


@router.post("/{event_id}/files/{fingerprint}/jpeg-render/full")
def jpeg_render_full(
    event_id: str,
    fingerprint: str,
    payload: JpegProductRenderRequest,
) -> Response:
    return _render_response(
        event_id,
        fingerprint,
        payload,
        "full",
    )


@router.post("/{event_id}/files/{fingerprint}/jpeg-render/assert-current")
def jpeg_render_assert_current(
    event_id: str,
    fingerprint: str,
    payload: JpegProductRenderRequest,
) -> dict[str, Any]:
    try:
        recipe_sha256 = assert_current_jpeg_revision(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=payload.recipe,
            revision=payload.revision,
        )
    except (
        JpegProductRenderError,
        JpegRecipeValidationError,
    ) as exc:
        _raise_render_http(exc)

    return {
        "current": True,
        "revision": payload.revision,
        "recipe_sha256": recipe_sha256,
    }
