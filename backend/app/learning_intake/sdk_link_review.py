"""PG-LI-02B.01: correlate Lightroom SDK-reported Smart Preview paths.

The SDK pilot emits a private local JSON describing selected 1..16 photos.
It remains a manual research readback, not a signed source identity proof.
This module never writes to Lightroom's catalog, DNG files, or RAW originals.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from app.learning_intake.service import LearningIntakeError

MAX_JSON_BYTES = 256 * 1024
MAX_PHOTOS = 16
SCHEMA = "prographer.lightroom.smart_preview_sdk_links.v1"


def verify_link_export(
    *, evidence_path: Path, catalog_path: Path,
    preview_root: Path, catalog_records: list[dict],
) -> dict:
    """Validate the SDK's photo_uuid→smartPreviewPath claims against local data.

    Reports only aggregate evidence. A user-editable JSON is NOT a signed
    attestation. Training eligibility remains false.
    """
    if evidence_path.suffix.casefold() != ".json" or evidence_path.is_symlink():
        raise LearningIntakeError("Choose a local research SDK evidence .json file.")
    try:
        size = evidence_path.stat().st_size
        if size > MAX_JSON_BYTES or size <= 0:
            raise LearningIntakeError("SDK evidence file is empty or too large.")
        data = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LearningIntakeError("Cannot parse Lightroom SDK evidence JSON.") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise LearningIntakeError("Wrong Lightroom SDK evidence schema.")
    actual_catalog = data.get("catalog_path")
    if not isinstance(actual_catalog, str):
        raise LearningIntakeError("SDK evidence lacks catalog identity.")
    try:
        sdk_catalog = Path(actual_catalog).resolve(strict=True)
        expected_catalog = catalog_path.resolve(strict=True)
    except OSError as exc:
        raise LearningIntakeError("SDK catalog is not accessible.") from exc
    if sdk_catalog != expected_catalog and str(sdk_catalog).casefold() != str(expected_catalog).casefold():
        raise LearningIntakeError("SDK evidence refers to another Lightroom catalog.")

    rows = data.get("records")
    if not isinstance(rows, list) or not (1 <= len(rows) <= MAX_PHOTOS):
        raise LearningIntakeError("SDK evidence must contain 1 to 16 selected photos.")
    catalog_map: dict[str, list[dict]] = {}
    for photo in catalog_records:
        ident = photo.get("catalog_global_image_id")
        if isinstance(ident, str):
            catalog_map.setdefault(ident.casefold(), []).append(photo)

    counts: Counter[str] = Counter()
    sample: list[dict] = []
    used_uuids: set[str] = set()
    used_paths: Counter[str] = Counter()
    validated_preview_root = preview_root.resolve(strict=True)

    for row in rows:
        if not isinstance(row, dict):
            raise LearningIntakeError("Invalid photo record in SDK evidence.")
        uuid = row.get("photo_uuid")
        preview = row.get("smart_preview_path")
        if not isinstance(uuid, str) or not 1 <= len(uuid) <= 128:
            raise LearningIntakeError("SDK photo UUID is invalid.")
        normalized = uuid.casefold()
        if normalized in used_uuids:
            raise LearningIntakeError("Duplicate SDK photo UUID; selection is ambiguous.")
        used_uuids.add(normalized)

        status = "unknown"
        if len(catalog_map.get(normalized, [])) != 1:
            status = "catalog_uuid_missing_or_ambiguous"
        elif not isinstance(preview, str) or not preview:
            status = "sdk_smart_preview_missing"
        else:
            try:
                path = Path(preview)
                if path.is_symlink():
                    status = "preview_symlink_rejected"
                else:
                    resolved = path.resolve(strict=True)
                    if not resolved.is_relative_to(validated_preview_root):
                        status = "outside_selected_smart_preview_root"
                    elif resolved.suffix.casefold() != ".dng" or not resolved.is_file():
                        status = "not_a_dng_file"
                    else:
                        with resolved.open("rb") as stream:
                            header = stream.read(4)
                        if header not in (b"II*\x00", b"MM\x00*"):
                            status = "not_a_dng_container"
                        else:
                            used_paths[str(resolved).casefold()] += 1
                            status = "sdk_path_and_catalog_uuid_correlated"
            except OSError:
                status = "preview_file_missing_or_unreadable"

        counts[status] += 1
        sample.append({
            "catalog_uuid": uuid,
            "status": status,
            "virtual_copy_requires_review": bool(row.get("is_virtual_copy")),
            "final_edit_verified": False,
            "neutral_start_verified": False,
            "training_eligible": False,
        })

    # Virtual copies can legitimately share a Smart Preview. That is a reason
    # for human review, never evidence of two independent training examples.
    shared = sum(n - 1 for n in used_paths.values() if n > 1)
    return {
        "schema": "prographer.learning_intake.sdk_link_review.v1",
        "status": "SDK_PATH_CORROBORATION_RESEARCH_ONLY",
        "selected_count": len(rows),
        "sdk_path_catalog_uuid_correlated": counts["sdk_path_and_catalog_uuid_correlated"],
        "shared_preview_extra_links": shared,
        "status_counts": dict(sorted(counts.items())),
        "records": sample,
        "source_raw_identity_verified": False,
        "approved_finality_verified": False,
        "neutral_start_verified": False,
        "training_ready_samples": 0,
        "warnings": [
            "SDK evidence file is a private user-supplied export, not a cryptographically signed attestation.",
            "SDK catalog photo UUID and preview DNG location can be corroborated, but not original RAW identity or edit finality.",
            "Develop targets, Import-vs-Reset state, virtual copies and whole-event splits still require approved Lightroom Bridge validation.",
        ],
    }
