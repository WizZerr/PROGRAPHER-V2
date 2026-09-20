from fastapi import APIRouter, HTTPException, status

from app.datasets.builder import build_dataset_preview
from app.datasets.manifest import write_manifest
from app.datasets.review import apply_review_decisions
from app.schemas.dataset import (
    DatasetManifestRequest,
    DatasetManifestResponse,
    DatasetPreviewRequest,
    DatasetPreviewResponse,
)

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
            "עדיין לא אומת שמדובר בעריכה הסופית של הצלם."
        ),
    )


@router.post("/manifest", response_model=DatasetManifestResponse)
def create_dataset_manifest(
    payload: DatasetManifestRequest,
) -> DatasetManifestResponse:
    try:
        preview = build_dataset_preview(
            raw_root=payload.raw_root,
            edits_root=payload.edits_root,
            event_id=payload.event_id,
        )

        decisions = {
            item.fingerprint: item.decision
            for item in payload.decisions
        }
        reviewed = apply_review_decisions(preview, decisions)
        manifest_id, manifest_path, _ = write_manifest([reviewed])
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    excluded_pairs = sum(
        candidate.pair_status == "matched"
        and not candidate.usable_for_training
        for candidate in reviewed.candidates
    )

    return DatasetManifestResponse(
        manifest_id=manifest_id,
        manifest_path=str(manifest_path),
        event_id=reviewed.event_id,
        raw_files=reviewed.raw_files,
        matched_pairs=reviewed.matched_pairs,
        verified_training_pairs=reviewed.verified_training_pairs,
        excluded_pairs=excluded_pairs,
        note=(
            "Manifest נשמר עם provenance והחלטות מפורשות. "
            "רק זוג שאומת כעריכה סופית וללא סיבת החרגה "
            "נספר כדוגמת אימון."
        ),
    )
