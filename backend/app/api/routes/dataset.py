from fastapi import APIRouter, HTTPException, status

from app.datasets.builder import build_dataset_preview
from app.datasets.contracts import DatasetRights
from app.datasets.coverage import summarize_coverage
from app.datasets.manifest import write_manifest
from app.datasets.review import apply_review_decisions
from app.schemas.dataset import (
    DatasetManifestRequest,
    DatasetManifestResponse,
    DatasetPreviewRequest,
    DatasetPreviewResponse,
)

router = APIRouter(prefix="/api/dataset", tags=["dataset"])


def _build_preview(payload: DatasetPreviewRequest):
    return build_dataset_preview(
        raw_root=payload.raw_root,
        edits_root=payload.edits_root,
        event_id=payload.event_id,
        photographer_id=payload.photographer_id,
        lightroom_version=payload.lightroom_version,
        style_label=payload.style_label,
    )


@router.post("/preview", response_model=DatasetPreviewResponse)
def preview_dataset(
    payload: DatasetPreviewRequest,
) -> DatasetPreviewResponse:
    try:
        preview = _build_preview(payload)
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
        preview = _build_preview(payload)

        decisions = {
            item.fingerprint: item.decision
            for item in payload.decisions
        }
        reviewed = apply_review_decisions(preview, decisions)

        rights = DatasetRights(
            permission_basis=payload.rights.permission_basis,
            allow_personal_training=payload.rights.allow_personal_training,
            allow_general_training=payload.rights.allow_general_training,
            license_name=payload.rights.license_name,
            notes=payload.rights.notes,
        )

        coverage = summarize_coverage(
            [reviewed],
            rights=rights,
        )

        manifest_id, manifest_path, _ = write_manifest(
            [reviewed],
            rights=rights,
        )
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
        usable_personal_training_pairs=(
            coverage.usable_personal_training_pairs
        ),
        excluded_pairs=excluded_pairs,
        readiness_state=coverage.readiness_state,
        readiness_reasons=list(coverage.readiness_reasons),
        note=(
            "Manifest נשמר עם Metadata, provenance, rights ו-coverage. "
            "חומר אישי אינו מורשה לאימון כללי אלא אם ניתנה לכך "
            "הרשאה מפורשת."
        ),
    )
