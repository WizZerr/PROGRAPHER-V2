from fastapi import APIRouter, HTTPException, status

from app.datasets.builder import build_dataset_preview
from app.schemas.dataset import DatasetPreviewRequest, DatasetPreviewResponse

router = APIRouter(prefix="/api/dataset", tags=["dataset"])


@router.post("/preview", response_model=DatasetPreviewResponse)
def preview_dataset(
    payload: DatasetPreviewRequest,
) -> DatasetPreviewResponse:
    try:
        preview = build_dataset_preview(
            raw_root=payload.raw_root,
            edits_root=payload.edits_root,
            event_id=payload.event_id,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return DatasetPreviewResponse(
        event_id=preview.event_id,
        raw_files=preview.raw_files,
        xmp_files=preview.xmp_files,
        matched_pairs=preview.matched_pairs,
        unmatched_raw=preview.unmatched_raw,
        ambiguous_raw=preview.ambiguous_raw,
        verified_training_pairs=preview.verified_training_pairs,
        note=(
            "Matched פירושו התאמה טכנית בלבד. "
            "עדיין לא אומת שמדובר בעריכה הסופית של הצלם, "
            "ולכן verified_training_pairs נשאר 0."
        ),
    )
