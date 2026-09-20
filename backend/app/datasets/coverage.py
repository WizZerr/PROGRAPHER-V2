from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.datasets.contracts import DatasetPreview, DatasetRights


@dataclass(frozen=True)
class DatasetCoverage:
    events: int
    raw_files: int
    matched_pairs: int
    verified_training_pairs: int
    usable_personal_training_pairs: int
    camera_models: dict[str, int]
    missing_camera_model: int
    missing_capture_time: int
    missing_raw_wb: int
    local_adjustment_exclusions: int
    incomplete_target_pairs: int
    lighting_coverage_status: str
    readiness_state: str
    readiness_reasons: tuple[str, ...]


def summarize_coverage(
    previews: list[DatasetPreview],
    *,
    rights: DatasetRights | None = None,
) -> DatasetCoverage:
    active_rights = rights or DatasetRights()

    candidates = [
        candidate
        for preview in previews
        for candidate in preview.candidates
    ]

    cameras: Counter[str] = Counter()
    missing_camera = 0
    missing_time = 0
    missing_wb = 0
    local_exclusions = 0
    incomplete_targets = 0

    for candidate in candidates:
        metadata = candidate.source_metadata

        if metadata and metadata.camera_model:
            cameras[metadata.camera_model] += 1
        else:
            missing_camera += 1

        if not metadata or not metadata.captured_at:
            missing_time += 1

        if not metadata or not metadata.raw_wb:
            missing_wb += 1

        if "local_adjustments_out_of_initial_scope" in candidate.exclusion_reasons:
            local_exclusions += 1

        if candidate.missing_target_fields:
            incomplete_targets += 1

    verified = sum(
        candidate.usable_for_training
        for candidate in candidates
    )

    usable_personal = (
        verified
        if active_rights.allow_personal_training
        else 0
    )

    reasons: list[str] = []

    if len(previews) < 2:
        reasons.append(
            "נדרש יותר מאירוע אחד כדי להעריך הכללה בין אירועים."
        )

    if verified == 0:
        reasons.append(
            "אין עדיין זוגות RAW ↔ Final Edit מאומתים וללא החרגות."
        )

    if not active_rights.allow_personal_training:
        reasons.append(
            "לא נרשמה הרשאה מפורשת לשימוש בחומר לאימון אישי."
        )

    if missing_camera:
        reasons.append(
            "בחלק מהדוגמאות חסר זיהוי מצלמה."
        )

    # Lighting coverage is intentionally not inferred from a count or EXIF.
    reasons.append(
        "כיסוי תאורה טרם נמדד; הוא ייקבע מנתוני אירועים/Scene Engine."
    )

    return DatasetCoverage(
        events=len(previews),
        raw_files=sum(item.raw_files for item in previews),
        matched_pairs=sum(item.matched_pairs for item in previews),
        verified_training_pairs=verified,
        usable_personal_training_pairs=usable_personal,
        camera_models=dict(sorted(cameras.items())),
        missing_camera_model=missing_camera,
        missing_capture_time=missing_time,
        missing_raw_wb=missing_wb,
        local_adjustment_exclusions=local_exclusions,
        incomplete_target_pairs=incomplete_targets,
        lighting_coverage_status="not_measured",
        readiness_state="needs_more_data" if reasons else "candidate_ready",
        readiness_reasons=tuple(reasons),
    )
