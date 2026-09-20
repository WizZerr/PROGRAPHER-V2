from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.datasets.contracts import SourceIdentity, TargetRecipe
from app.ingest.scanner import scan_event_folder
from app.lightroom_bridge.xmp_roundtrip import run_reference_roundtrip
from app.reference.store import register_lightroom_render
from app.schemas.reference import (
    RegisterReferenceRequest,
    RegisterReferenceResponse,
    RoundTripRequest,
    RoundTripResponse,
)

router = APIRouter(prefix="/api/reference", tags=["reference"])


def _recipe(payload) -> TargetRecipe:
    return TargetRecipe(
        exposure=payload.exposure,
        temperature=payload.temperature,
        tint=payload.tint,
        blacks=payload.blacks,
        process_version=payload.process_version,
        camera_profile=payload.camera_profile,
    )


def _source_identity_for_file(path: str) -> SourceIdentity:
    raw = Path(path).expanduser().resolve(strict=True)

    records = scan_event_folder(raw.parent)

    matches = [
        item
        for item in records
        if Path(item.absolute_path).resolve() == raw
    ]

    if len(matches) != 1:
        raise ValueError(
            "לא ניתן ליצור זהות מקור חד-משמעית לקובץ RAW שנבחר."
        )

    item = matches[0]

    if item.source_type != "raw":
        raise ValueError("הקובץ שנבחר אינו RAW נתמך.")

    return SourceIdentity(
        absolute_path=item.absolute_path,
        relative_path=item.relative_path,
        filename=item.filename,
        extension=item.extension,
        size_bytes=item.size_bytes,
        modified_ns=item.modified_ns,
        fingerprint=item.fingerprint,
    )


@router.post("/roundtrip", response_model=RoundTripResponse)
def reference_roundtrip(
    payload: RoundTripRequest,
) -> RoundTripResponse:
    try:
        result = run_reference_roundtrip(
            raw_path=payload.raw_path,
            recipe=_recipe(payload.recipe),
            output_dir=payload.output_dir,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return RoundTripResponse(
        source_fingerprint=result.source_fingerprint,
        written_xmp_path=result.written_xmp_path,
        source_unchanged=result.source_unchanged,
        recipe_matches=result.recipe_matches,
        mismatches=list(result.mismatches),
        note=(
            "זהו Round-trip טכני של XMP ב-ProGrapher. "
            "הוא אינו נחשב עדיין להוכחת Lightroom עד שהקובץ נבדק "
            "ב-Lightroom Classic ונרשם רינדור Reference."
        ),
    )


@router.post(
    "/lightroom-render",
    response_model=RegisterReferenceResponse,
)
def reference_lightroom_render(
    payload: RegisterReferenceRequest,
) -> RegisterReferenceResponse:
    try:
        source = _source_identity_for_file(payload.raw_path)
        case, manifest = register_lightroom_render(
            source=source,
            recipe=_recipe(payload.recipe),
            render_path=payload.render_path,
            color_space=payload.color_space,
            file_format=payload.file_format,
            process_family=payload.process_family,
            lightroom_version=payload.lightroom_version,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    assert case.render is not None

    return RegisterReferenceResponse(
        case_id=case.case_id,
        manifest_path=str(manifest),
        render_sha256=case.render.render_sha256,
        status=case.status,
        note=(
            "רינדור Lightroom נרשם כ-Reference נפרד. "
            "הקובץ אינו מועתק ואינו הופך אוטומטית לתווית אימון."
        ),
    )
