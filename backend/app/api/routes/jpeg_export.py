from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.rendering.jpeg_export import (
    JpegExportError,
    JpegExportOptions,
    encode_jpeg_export,
)
from app.rendering.jpeg_product_render import (
    JpegRenderRevisionConflict,
    JpegRenderSourceUnavailable,
    JpegRenderStaleRevision,
)
from app.rendering.jpeg_renderer import JpegRecipeValidationError


router = APIRouter(prefix="/api/events", tags=["jpeg-export"])


class JpegExportOptionsRequest(BaseModel):
    quality: int = Field(default=95, ge=1, le=100)
    max_edge: int | None = Field(default=None, ge=1)
    icc_policy: Literal["embed_srgb", "omit"] = "embed_srgb"
    metadata_policy: Literal["preserve", "strip"] = "preserve"
    include_gps: bool = False


class JpegExportEncodeRequest(BaseModel):
    revision: int = Field(ge=1)
    recipe: dict[str, Any]
    options: JpegExportOptionsRequest = Field(
        default_factory=JpegExportOptionsRequest
    )


@router.post("/{event_id}/files/{fingerprint}/jpeg-export/encode")
def encode_export(
    event_id: str,
    fingerprint: str,
    payload: JpegExportEncodeRequest,
) -> Response:
    try:
        artifact = encode_jpeg_export(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=payload.recipe,
            revision=payload.revision,
            options=JpegExportOptions(**payload.options.model_dump()),
        )
    except (
        JpegRenderStaleRevision,
        JpegRenderRevisionConflict,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except JpegRenderSourceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        JpegExportError,
        JpegRecipeValidationError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return Response(
        content=artifact.payload,
        media_type=artifact.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-ProGrapher-JPEG-Export-Contract": artifact.contract_version,
            "X-ProGrapher-Recipe-Revision": str(artifact.revision),
            "X-ProGrapher-Recipe-SHA256": artifact.recipe_sha256,
            "X-ProGrapher-Export-Width": str(artifact.width),
            "X-ProGrapher-Export-Height": str(artifact.height),
            "X-ProGrapher-JPEG-Quality": str(artifact.quality),
            "X-ProGrapher-ICC-Policy": artifact.icc_policy,
            "X-ProGrapher-Metadata-Policy": artifact.metadata_policy,
            "X-ProGrapher-GPS-Included": str(
                artifact.gps_included
            ).lower(),
        },
    )
