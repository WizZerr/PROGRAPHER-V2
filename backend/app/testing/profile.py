from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.datasets.builder import build_dataset_preview
from app.datasets.contracts import TargetRecipe
from app.platform.paths import user_data_dir
from app.schemas.testing import (
    BaselineValues,
    ExportFileResult,
    ExportRecipeItem,
    ExportRecipesResponse,
    RecipeValues,
    ReviewFile,
    ReviewSheet,
    TestingProfileSummary,
)
from app.services.event_service import EventOpenError, list_event_files
from app.catalog.event_store import EventStore
from app.testing.jpeg_pairs import JPEG_EXTENSIONS, scan_jpeg_pairs
from app.testing.sidecar import SidecarExportError, write_testing_sidecar


PROFILE_NOTE = (
    "זהו בסיס חציון של Exposure, Temperature ו-Tint מזוגות RAW שזוהו באופן חד. "
    "אותו מתכון מוצע לכל תמונה. זו אינה עריכה לפי תמונה, ואין כאן טענת איכות."
)
JPEG_PROFILE_NOTE = (
    "מאגר JPEG נפרד ממסלול RAW. נשמרים רק זוגות חד-משמעיים של JPEG מקורי "
    "ו-JPEG ערוך במניפסט נתונים. עדיין אין כאן מודל מאומן או מתכון Lightroom."
)
JPEG_REVIEW_NOTE = (
    "פרופיל JPEG. מוצגים רק קובצי JPEG. אין מתכון Lightroom ואין ייצוא XMP."
)
REVIEW_NOTE = (
    "ההצעה היא בסיס הבדיקה, אם נבנה. עריכת הצלם מוצגת בנפרד כשיש XMP תואם. "
    "תצוגה מקומית אינה התוצאה של Lightroom."
)
EXPORT_NOTE = (
    "קובצי ה-XMP נכתבו לתיקייה שנבחרה. קובצי ה-RAW לא נפתחו לכתיבה. "
    "כדי לבדוק ב-Lightroom יש להניח את ה-XMP ליד קובץ המקור באותו שם."
)
TUNING_PAIR_THRESHOLD = 30


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def profile_path() -> Path:
    return user_data_dir() / "testing_profile.json"


def _dataset_manifest_path(profile_id: str) -> Path:
    return user_data_dir() / "testing_datasets" / profile_id / "manifest.json"


def _write_jpeg_manifest(
    *,
    profile_id: str,
    created_at: str,
    photographer_id: str,
    event_label: str,
    originals_root: str,
    edits_root: str,
    scan,
) -> Path:
    path = _dataset_manifest_path(profile_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "kind": "jpeg_pairs",
        "profile_id": profile_id,
        "created_at": created_at,
        "photographer_id": photographer_id,
        "event_label": event_label or "reference",
        "originals_root": originals_root,
        "edits_root": edits_root,
        "pairs": [
            {
                "original_path": pair.original_path,
                "edited_path": pair.edited_path,
                "original_relative_path": pair.original_relative_path,
                "edited_relative_path": pair.edited_relative_path,
                "original_fingerprint": pair.original_fingerprint,
                "edited_fingerprint": pair.edited_fingerprint,
            }
            for pair in scan.pairs
        ],
    }
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def _empty_profile_document() -> dict:
    return {
        "active_source": "raw",
        "profiles": {},
        "reviews": {"raw": {}, "jpeg": {}},
    }


def _normalize_profile_document(document: dict) -> dict:
    if "profiles" in document:
        normalized = _empty_profile_document()
        normalized["active_source"] = document.get("active_source") or "raw"
        normalized["profiles"] = dict(document.get("profiles") or {})
        reviews = document.get("reviews") or {}
        normalized["reviews"] = {
            "raw": dict(reviews.get("raw") or {}),
            "jpeg": dict(reviews.get("jpeg") or {}),
        }
        return normalized

    # Backward-compatible migration from the first PR format:
    # {"summary": <one profile>, "reviews": {...}}
    summary = document.get("summary")
    if not isinstance(summary, dict):
        return _empty_profile_document()

    source = summary.get("learning_source") or "raw"
    normalized = _empty_profile_document()
    normalized["active_source"] = source
    normalized["profiles"][source] = summary
    normalized["reviews"][source] = dict(document.get("reviews") or {})
    return normalized


def load_profile_document() -> dict | None:
    path = profile_path()
    if not path.exists():
        return None
    return _normalize_profile_document(
        json.loads(path.read_text(encoding="utf-8"))
    )


def _write_document(document: dict) -> None:
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _reviews_for(document: dict, learning_source: str) -> dict:
    reviews = document.setdefault("reviews", {"raw": {}, "jpeg": {}})
    source_reviews = reviews.get(learning_source)
    if not isinstance(source_reviews, dict):
        source_reviews = {}
        reviews[learning_source] = source_reviews
    return source_reviews


def _recipe_from_target(recipe: TargetRecipe | None) -> RecipeValues | None:
    if recipe is None:
        return None
    if (
        recipe.exposure is None
        and recipe.temperature is None
        and recipe.tint is None
    ):
        return None
    return RecipeValues(
        exposure=recipe.exposure,
        temperature=recipe.temperature,
        tint=recipe.tint,
        process_version=recipe.process_version,
        camera_profile=recipe.camera_profile,
    )


def _complete(recipe: RecipeValues | None) -> bool:
    return (
        recipe is not None
        and recipe.exposure is not None
        and recipe.temperature is not None
        and recipe.tint is not None
    )


def _baseline_recipe(baseline: BaselineValues | None) -> RecipeValues | None:
    if baseline is None:
        return None
    return RecipeValues(
        exposure=baseline.exposure,
        temperature=baseline.temperature,
        tint=baseline.tint,
    )


def _round_exposure(value: float) -> float:
    return round(float(value), 2)


def _persist_profile(summary: TestingProfileSummary) -> None:
    document = load_profile_document() or _empty_profile_document()
    profiles = dict(document.get("profiles") or {})
    profiles[summary.learning_source] = summary.model_dump()
    document["profiles"] = profiles
    document["active_source"] = summary.learning_source
    _reviews_for(document, summary.learning_source)
    _write_document(document)


def _profile_id(identity: dict) -> str:
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]


def _build_jpeg_testing_profile(
    *,
    raw_root: str,
    edits_root: str,
    photographer_id: str,
    event_label: str,
) -> TestingProfileSummary:
    try:
        scan = scan_jpeg_pairs(raw_root, edits_root)
    except (OSError, ValueError) as exc:
        raise ValueError(str(exc)) from exc

    warnings = [
        "אין טענת איכות. לפרופיל JPEG אין בסיס Lightroom.",
    ]
    if scan.ignored_non_jpeg:
        warnings.append(
            f"{scan.ignored_non_jpeg} קבצים שאינם JPEG לא נכנסו לפרופיל."
        )
    if scan.ambiguous_files:
        warnings.append(
            f"{scan.ambiguous_files} קבצים לא שובצו כי אותו שם הופיע יותר מפעם אחת."
        )
    if scan.unmatched_files:
        warnings.append(
            f"{scan.unmatched_files} קובצי JPEG מקור בלי JPEG ערוך תואם לא נכנסו."
        )
    if scan.identical_pairs:
        warnings.append(
            f"{scan.identical_pairs} זוגות זהים לחלוטין נפסלו כי מקור וערוך הם אותו קובץ."
        )
    if scan.matched_pairs == 0:
        warnings.append("אין זוגות JPEG חד-משמעיים.")
    elif scan.matched_pairs < TUNING_PAIR_THRESHOLD:
        warnings.append(
            "פחות מ-30 זוגות שמישים. אפשר לבדוק את המסלול, אבל אי אפשר לכוון סגנון מהמדגם הזה."
        )

    created_at = _utc_now()
    identity = {
        "learning_source": "jpeg",
        "raw_root": str(Path(raw_root).expanduser().resolve()),
        "edits_root": str(Path(edits_root).expanduser().resolve()),
        "photographer_id": photographer_id,
        "event_label": event_label or "reference",
        "pairs": [
            [pair.original_fingerprint, pair.edited_fingerprint]
            for pair in scan.pairs
        ],
    }
    profile_id = _profile_id(identity)
    manifest_path = _write_jpeg_manifest(
        profile_id=profile_id,
        created_at=created_at,
        photographer_id=photographer_id,
        event_label=event_label,
        originals_root=identity["raw_root"],
        edits_root=identity["edits_root"],
        scan=scan,
    )
    return TestingProfileSummary(
        profile_id=profile_id,
        created_at=created_at,
        photographer_id=photographer_id,
        learning_source="jpeg",
        learning_material="jpeg_pairs",
        dataset_manifest_path=str(manifest_path),
        raw_root=identity["raw_root"],
        edits_root=identity["edits_root"],
        event_label=event_label or "reference",
        raw_files=scan.original_files,
        xmp_files=scan.edited_files,
        matched_pairs=scan.matched_pairs,
        ambiguous_raw=scan.ambiguous_files,
        unmatched_raw=scan.unmatched_files,
        usable_pairs=scan.matched_pairs,
        excluded_local_adjustments=0,
        excluded_missing_targets=0,
        baseline=None,
        quality_claim_allowed=False,
        warnings=warnings,
        note=JPEG_PROFILE_NOTE,
    )


def build_testing_profile(
    *,
    raw_root: str,
    edits_root: str,
    photographer_id: str,
    event_label: str,
    learning_source: Literal["raw", "jpeg"] = "raw",
) -> TestingProfileSummary:
    if learning_source == "jpeg":
        summary = _build_jpeg_testing_profile(
            raw_root=raw_root,
            edits_root=edits_root,
            photographer_id=photographer_id,
            event_label=event_label,
        )
        _persist_profile(summary)
        return summary
    try:
        preview = build_dataset_preview(
            raw_root=raw_root,
            edits_root=edits_root,
            event_id=event_label or "reference",
            photographer_id=photographer_id,
            include_metadata=False,
        )
    except (OSError, ValueError) as exc:
        raise ValueError(str(exc)) from exc

    usable_exposure: list[float] = []
    usable_temperature: list[int] = []
    usable_tint: list[int] = []
    excluded_local = 0
    excluded_missing = 0
    shared_xmp = {
        path
        for path, count in Counter(
            candidate.xmp_path
            for candidate in preview.candidates
            if candidate.xmp_path
        ).items()
        if count > 1
    }
    excluded_shared = 0

    for candidate in preview.candidates:
        if candidate.xmp_path in shared_xmp:
            excluded_shared += 1
            continue
        if candidate.pair_status != "matched" or candidate.target_recipe is None:
            continue
        if candidate.has_local_adjustments:
            excluded_local += 1
            continue
        if candidate.missing_target_fields:
            excluded_missing += 1
            continue
        recipe = candidate.target_recipe
        if (
            recipe.exposure is None
            or recipe.temperature is None
            or recipe.tint is None
        ):
            excluded_missing += 1
            continue
        usable_exposure.append(float(recipe.exposure))
        usable_temperature.append(int(recipe.temperature))
        usable_tint.append(int(recipe.tint))

    baseline: BaselineValues | None = None
    if usable_exposure:
        baseline = BaselineValues(
            exposure=_round_exposure(statistics.median(usable_exposure)),
            temperature=int(round(statistics.median(usable_temperature))),
            tint=int(round(statistics.median(usable_tint))),
            sample_count=len(usable_exposure),
        )

    warnings: list[str] = [
        "אין טענת איכות. המדדים יופיעו רק אחרי השוואה לעריכות הצלם.",
    ]
    if preview.ambiguous_raw:
        warnings.append(
            f"{preview.ambiguous_raw} קבצים לא שובצו כי אותו שם הופיע יותר מפעם אחת."
        )
    if preview.unmatched_raw:
        warnings.append(
            f"{preview.unmatched_raw} קבצי RAW בלי XMP תואם לא נכנסו לבסיס."
        )
    if excluded_missing:
        warnings.append(
            f"{excluded_missing} זוגות חסרים Exposure, Temperature או Tint ונשמרו כחסרים, לא כאפס."
        )
    if excluded_shared:
        warnings.append(
            f"{excluded_shared} קבצים חולקים אותו XMP ולא נכנסו לבסיס."
        )
    if excluded_local:
        warnings.append(
            f"{excluded_local} זוגות עם התאמות מקומיות הוצאו מבסיס שלושת היעדים."
        )
    if baseline is None:
        warnings.append("אין עדיין בסיס. צריך לפחות זוג אחד עם שלושת היעדים.")
    elif baseline.sample_count < TUNING_PAIR_THRESHOLD:
        warnings.append(
            "פחות מ-30 זוגות שמישים. אפשר לבדוק את המסלול, אבל אי אפשר לכוון סגנון מהמדגם הזה."
        )

    created_at = _utc_now()
    identity = {
        "learning_source": "raw",
        "raw_root": str(Path(raw_root).expanduser().resolve()),
        "edits_root": str(Path(edits_root).expanduser().resolve()),
        "photographer_id": photographer_id,
        "event_label": event_label or "reference",
        "source_fingerprints": sorted(
            candidate.source.fingerprint
            for candidate in preview.candidates
        ),
        "usable_pairs": len(usable_exposure),
        "baseline": baseline.model_dump() if baseline else None,
    }

    summary = TestingProfileSummary(
        profile_id=_profile_id(identity),
        created_at=created_at,
        photographer_id=photographer_id,
        learning_source="raw",
        learning_material="raw_xmp",
        dataset_manifest_path=None,
        raw_root=identity["raw_root"],
        edits_root=identity["edits_root"],
        event_label=event_label or "reference",
        raw_files=preview.raw_files,
        xmp_files=preview.xmp_files,
        matched_pairs=preview.matched_pairs,
        ambiguous_raw=preview.ambiguous_raw,
        unmatched_raw=preview.unmatched_raw,
        usable_pairs=len(usable_exposure),
        excluded_local_adjustments=excluded_local,
        excluded_missing_targets=excluded_missing,
        baseline=baseline,
        quality_claim_allowed=False,
        warnings=warnings,
        note=PROFILE_NOTE,
    )

    _persist_profile(summary)
    return summary


def active_testing_profile(
    learning_source: Literal["raw", "jpeg"] | None = None,
) -> TestingProfileSummary | None:
    document = load_profile_document()
    if not document:
        return None
    source = learning_source or document.get("active_source") or "raw"
    summary = (document.get("profiles") or {}).get(source)
    if not isinstance(summary, dict):
        return None
    return TestingProfileSummary.model_validate(summary)


def build_review_sheet(event_id: str) -> ReviewSheet:
    store = EventStore()
    try:
        event = store.get_event(event_id)
        files = list_event_files(event_id, store)
    except (KeyError, EventOpenError) as exc:
        raise ValueError("האירוע לא נמצא.") from exc

    profile = active_testing_profile()
    learning_source = profile.learning_source if profile else "raw"
    if learning_source == "jpeg":
        rows = [
            ReviewFile(
                fingerprint=item.fingerprint,
                filename=item.filename,
                relative_path=item.relative_path,
                absolute_path=item.absolute_path,
                pair_status="jpeg",
                photographer=None,
                baseline=None,
                saved_review=None,
                suggested=None,
                exclusion_reasons=["no_lightroom_recipe"],
            )
            for item in files
            if item.source_type == "rendered" and item.extension in JPEG_EXTENSIONS
        ]
        return ReviewSheet(
            event_id=event.id,
            event_name=event.name,
            learning_source="jpeg",
            quality_claim_allowed=False,
            baseline=None,
            files=rows,
            note=JPEG_REVIEW_NOTE,
        )

    baseline = profile.baseline if profile else None
    baseline_recipe = _baseline_recipe(baseline)
    document = load_profile_document() or _empty_profile_document()
    reviews = _reviews_for(document, "raw")

    preview = build_dataset_preview(
        raw_root=event.root_path,
        edits_root=event.root_path,
        event_id=event.id,
        include_metadata=False,
    )
    shared_xmp = {
        path
        for path, count in Counter(
            candidate.xmp_path
            for candidate in preview.candidates
            if candidate.xmp_path
        ).items()
        if count > 1
    }
    by_fingerprint = {
        candidate.source.fingerprint: candidate
        for candidate in preview.candidates
    }

    rows: list[ReviewFile] = []
    for item in files:
        if item.source_type != "raw":
            continue
        candidate = by_fingerprint.get(item.fingerprint)
        shared = bool(candidate and candidate.xmp_path in shared_xmp)
        photographer = None if shared else _recipe_from_target(
            candidate.target_recipe if candidate else None
        )
        saved_raw = reviews.get(f"{event_id}:{item.fingerprint}")
        saved = (
            RecipeValues.model_validate(saved_raw["recipe"])
            if isinstance(saved_raw, dict) and saved_raw.get("recipe")
            else None
        )
        if _complete(saved):
            suggested = saved
        elif baseline_recipe is not None:
            suggested = baseline_recipe
        elif _complete(photographer):
            suggested = photographer
        else:
            suggested = None

        rows.append(
            ReviewFile(
                fingerprint=item.fingerprint,
                filename=item.filename,
                relative_path=item.relative_path,
                absolute_path=item.absolute_path,
                pair_status=(
                    "ambiguous"
                    if shared
                    else candidate.pair_status if candidate else "unmatched"
                ),
                photographer=photographer,
                baseline=baseline_recipe,
                saved_review=saved,
                suggested=suggested,
                exclusion_reasons=(
                    ["ambiguous_pair"]
                    if shared
                    else list(candidate.exclusion_reasons)
                    if candidate
                    else ["missing_edit_pair"]
                ),
            )
        )

    return ReviewSheet(
        event_id=event.id,
        event_name=event.name,
        learning_source="raw",
        quality_claim_allowed=False,
        baseline=baseline,
        files=rows,
        note=REVIEW_NOTE,
    )


def export_testing_recipes(
    *,
    event_id: str,
    output_dir: str,
    items: list[ExportRecipeItem],
) -> ExportRecipesResponse:
    profile = active_testing_profile()
    if profile is not None and profile.learning_source == "jpeg":
        raise ValueError("פרופיל JPEG לא מייצא מתכון Lightroom.")

    sheet = build_review_sheet(event_id)
    by_fingerprint = {item.fingerprint: item for item in sheet.files}
    results: list[ExportFileResult] = []
    document = load_profile_document() or _empty_profile_document()
    reviews = _reviews_for(document, "raw")

    for item in items:
        source = by_fingerprint.get(item.fingerprint)
        if source is None:
            results.append(
                ExportFileResult(
                    fingerprint=item.fingerprint,
                    status="skipped",
                    path=None,
                    reason="הקובץ לא נמצא באירוע.",
                    source_unchanged=True,
                )
            )
            continue

        photographer = source.photographer
        recipe = TargetRecipe(
            exposure=float(item.exposure),
            temperature=int(item.temperature),
            tint=int(item.tint),
            blacks=None,
            process_version=(
                photographer.process_version if photographer else None
            ),
            camera_profile=(
                photographer.camera_profile if photographer else None
            ),
        )
        try:
            written = write_testing_sidecar(
                raw_path=source.absolute_path,
                relative_path=source.relative_path,
                recipe=recipe,
                output_dir=output_dir,
            )
        except SidecarExportError as exc:
            results.append(
                ExportFileResult(
                    fingerprint=item.fingerprint,
                    status="skipped",
                    path=None,
                    reason=str(exc),
                    source_unchanged=True,
                )
            )
            continue

        saved_recipe = RecipeValues(
            exposure=recipe.exposure,
            temperature=recipe.temperature,
            tint=recipe.tint,
            process_version=recipe.process_version,
            camera_profile=recipe.camera_profile,
        )
        reviews[f"{event_id}:{item.fingerprint}"] = {
            "decision": item.decision,
            "recipe": saved_recipe.model_dump(),
            "exported_path": str(written),
            "updated_at": _utc_now(),
        }
        results.append(
            ExportFileResult(
                fingerprint=item.fingerprint,
                status="written",
                path=str(written),
                reason=None,
                source_unchanged=True,
            )
        )

    document.setdefault("reviews", {"raw": {}, "jpeg": {}})["raw"] = reviews
    _write_document(document)

    written_count = sum(item.status == "written" for item in results)
    return ExportRecipesResponse(
        event_id=event_id,
        output_dir=str(Path(output_dir).expanduser().resolve()),
        written=written_count,
        skipped=len(results) - written_count,
        files=results,
        note=EXPORT_NOTE,
    )
