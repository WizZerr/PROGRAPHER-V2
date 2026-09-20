from fastapi import APIRouter, HTTPException, status

from app.schemas.metadata import MetadataReadRequest, PhotoMetadata
from app.services.metadata_service import MetadataReadError, read_photo_metadata

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


@router.post("/read", response_model=PhotoMetadata)
def read_metadata(payload: MetadataReadRequest) -> PhotoMetadata:
    try:
        return read_photo_metadata(payload.path)
    except MetadataReadError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
