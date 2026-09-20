from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.datasets.contracts import TargetRecipe
from app.ingest.scanner import scan_event_folder
from app.lightroom_bridge.xmp_roundtrip import write_reference_xmp


@dataclass(frozen=True)
class ObservedLightroomRecipe:
    exposure: float
    temperature: int
    tint: int
    blacks: float
    process_version: str
    camera_profile: str


@dataclass(frozen=True)
class VerificationResult:
    status: str
    source_unchanged: bool
    fixture_raw_unchanged: bool
    recipe_matches: bool
    render_exists: bool
    mismatches: tuple[str, ...]
    render_path: str | None
    render_sha256: str | None
    xmp_present: bool
    acr_present: bool


PROCESS_VERSION_UI_LABELS = {
    "5.0": "Version 1",
    "5.7": "Version 2",
    "6.6": "Version 3 (beta)",
    "6.7": "Version 3",
    "10.0": "Version 4",
    "11.0": "Version 5",
    "15.4": "Version 6 (Current)",
}


DEFAULT_REFERENCE_RECIPE = TargetRecipe(
    exposure=0.35,
    temperature=5650,
    tint=-7,
    blacks=-40.0,
    process_version="11.0",
    # Adobe Color is not a literal DCP CameraProfile name in XMP.
    # For this transport/reference test use the real base camera profile.
    camera_profile="Adobe Standard",
)


def process_version_ui_label(internal_version: str | None) -> str:
    if internal_version is None:
        return ""
    return PROCESS_VERSION_UI_LABELS.get(
        internal_version,
        internal_version,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def _default_workspace_root() -> Path:
    return Path.home() / "Desktop" / "ProGrapher Lightroom Reference"


def _pick_raw(folder: Path) -> Path:
    records = [
        item
        for item in scan_event_folder(folder)
        if item.source_type == "raw"
    ]

    if not records:
        raise ValueError("לא נמצא RAW נתמך בתיקייה שנבחרה.")

    records.sort(key=lambda item: item.relative_path.casefold())
    return Path(records[0].absolute_path).resolve(strict=True)


def _instructions(
    *,
    workspace: Path,
    fixture_raw: Path,
    expected: TargetRecipe,
) -> str:
    render_dir = workspace / "render"
    process_label = process_version_ui_label(expected.process_version)

    return f"""ProGrapher — Lightroom Reference Exercise — Windows

חשוב:
- עובדים רק על עותק הבדיקה שבתיקייה הזו.
- אין לייבא את קובץ המקור המקורי.
- ה-XMP נמצא ליד עותק ה-RAW כדי ש-Lightroom יוכל לקרוא אותו.
- החל מ-Lightroom Classic 15 ייתכן שייווצר גם קובץ ACR sidecar; זה תקין.

קובץ לבדיקה:
{fixture_raw}

שלב 1 — Lightroom Classic
1. פתח Lightroom Classic.
2. File > Import Photos And Video.
3. בחר את התיקייה:
   {fixture_raw.parent}
4. בחר ADD, לא Copy/Move, וייבא את קובץ הבדיקה.
5. פתח אותו ב-Develop.

הערכים שאנחנו מצפים לראות:
Exposure: {expected.exposure}
Temperature: {expected.temperature}
Tint: {expected.tint}
Blacks: {expected.blacks}
Process: {process_label}
Camera Profile: {expected.camera_profile}

אם הערכים אינם נטענים אוטומטית:
- אל תשנה אותם ידנית.
- עצור ודווח מה Lightroom מציג.

שלב 2 — Reference Render
אם הערכים תואמים ואין הודעת Profile missing:
1. Export את התמונה כ-JPEG.
2. Color Space: sRGB.
3. ללא Resize.
4. שמור לתיקייה:
   {render_dir}
5. רצוי שיהיה שם רק קובץ JPEG/TIFF אחד.

שלב 3 — חזור ל-CMD והריץ verify על ה-workspace הזה:
{workspace}

ב-verify תתבקש להקליד את הערכים שראית בפועל ב-Lightroom.
עבור Process הקלד את הטקסט שמופיע בממשק, למשל: Version 5.
"""


def create_exercise(
    *,
    raw_path: str | Path | None = None,
    raw_folder: str | Path | None = None,
    workspace_root: str | Path | None = None,
    recipe: TargetRecipe = DEFAULT_REFERENCE_RECIPE,
) -> Path:
    if (raw_path is None) == (raw_folder is None):
        raise ValueError(
            "יש לבחור בדיוק אחד: raw_path או raw_folder."
        )

    if raw_path is not None:
        source_raw = Path(raw_path).expanduser().resolve(strict=True)
        if not source_raw.is_file():
            raise ValueError("נתיב ה-RAW אינו קובץ.")
    else:
        source_folder = Path(raw_folder).expanduser().resolve(strict=True)
        if not source_folder.is_dir():
            raise ValueError("תיקיית ה-RAW אינה קיימת.")
        source_raw = _pick_raw(source_folder)

    root = (
        Path(workspace_root).expanduser().resolve()
        if workspace_root is not None
        else _default_workspace_root()
    )
    root.mkdir(parents=True, exist_ok=True)

    exercise_id = (
        datetime.now().strftime("%Y%m%d-%H%M%S")
        + "-"
        + uuid4().hex[:8]
    )
    workspace = root / exercise_id
    fixture_dir = workspace / "fixture"
    render_dir = workspace / "render"
    fixture_dir.mkdir(parents=True)
    render_dir.mkdir(parents=True)

    source_sha256 = _sha256(source_raw)

    fixture_raw = fixture_dir / source_raw.name
    shutil.copy2(source_raw, fixture_raw)

    fixture_sha256 = _sha256(fixture_raw)
    if fixture_sha256 != source_sha256:
        raise OSError("עותק ה-RAW אינו זהה למקור.")

    generated_xmp = write_reference_xmp(
        raw_path=fixture_raw,
        recipe=recipe,
        output_dir=fixture_dir,
    )
    sidecar_xmp = fixture_raw.with_suffix(".xmp")
    os.replace(generated_xmp, sidecar_xmp)

    if _sha256(source_raw) != source_sha256:
        raise OSError("קובץ המקור השתנה בזמן הכנת הבדיקה.")

    manifest = {
        "schema": "prographer.lightroom-reference-exercise.v1",
        "version": 2,
        "exercise_id": exercise_id,
        "created_at": _utc_now(),
        "platform": "windows_reference_exercise",
        "source_raw": str(source_raw),
        "source_sha256_before": source_sha256,
        "fixture_raw": str(fixture_raw),
        "fixture_raw_sha256_before": fixture_sha256,
        "fixture_xmp": str(sidecar_xmp),
        "render_dir": str(render_dir),
        "expected_recipe": asdict(recipe),
        "expected_lightroom_ui": {
            "process": process_version_ui_label(recipe.process_version),
            "camera_profile": recipe.camera_profile,
        },
        "status": "prepared",
    }

    manifest_path = workspace / "exercise.json"
    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    (workspace / "LIGHTROOM_STEPS.txt").write_text(
        _instructions(
            workspace=workspace,
            fixture_raw=fixture_raw,
            expected=recipe,
        ),
        encoding="utf-8",
    )

    return workspace


def _find_render(render_dir: Path) -> Path | None:
    supported = {
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
    }
    files = sorted(
        [
            path
            for path in render_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in supported
        ],
        key=lambda path: path.name.casefold(),
    )

    if not files:
        return None

    if len(files) > 1:
        raise ValueError(
            "נמצא יותר מרינדור אחד. השאר רק JPEG/TIFF אחד בתיקיית render."
        )

    return files[0]


def _normalize_ui(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _compare_recipe(
    expected: dict,
    observed: ObservedLightroomRecipe,
) -> tuple[str, ...]:
    mismatches: list[str] = []

    if abs(float(expected["exposure"]) - observed.exposure) > 1e-6:
        mismatches.append("exposure")

    if int(expected["temperature"]) != observed.temperature:
        mismatches.append("temperature")

    if int(expected["tint"]) != observed.tint:
        mismatches.append("tint")

    if abs(float(expected["blacks"]) - observed.blacks) > 1e-6:
        mismatches.append("blacks")

    expected_process = process_version_ui_label(
        str(expected["process_version"])
    )
    if _normalize_ui(expected_process) != _normalize_ui(
        observed.process_version
    ):
        mismatches.append("process_version")

    if _normalize_ui(str(expected["camera_profile"])) != _normalize_ui(
        observed.camera_profile
    ):
        mismatches.append("camera_profile")

    return tuple(mismatches)


def verify_exercise(
    *,
    workspace: str | Path,
    observed: ObservedLightroomRecipe,
    render_path: str | Path | None = None,
) -> VerificationResult:
    workspace_path = Path(workspace).expanduser().resolve(strict=True)
    manifest_path = workspace_path / "exercise.json"

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    source_raw = Path(manifest["source_raw"])
    fixture_raw = Path(manifest["fixture_raw"])
    fixture_xmp = Path(manifest["fixture_xmp"])

    source_unchanged = (
        source_raw.exists()
        and _sha256(source_raw)
        == manifest["source_sha256_before"]
    )

    fixture_unchanged = (
        fixture_raw.exists()
        and _sha256(fixture_raw)
        == manifest["fixture_raw_sha256_before"]
    )

    mismatches = _compare_recipe(
        manifest["expected_recipe"],
        observed,
    )

    if render_path is not None:
        render = Path(render_path).expanduser().resolve(strict=True)
    else:
        render = _find_render(Path(manifest["render_dir"]))

    render_exists = bool(render and render.is_file())
    render_sha256 = _sha256(render) if render_exists and render else None

    acr = fixture_raw.with_suffix(".acr")

    result = VerificationResult(
        status=(
            "PASS"
            if (
                source_unchanged
                and fixture_unchanged
                and not mismatches
                and render_exists
            )
            else "FAIL"
        ),
        source_unchanged=source_unchanged,
        fixture_raw_unchanged=fixture_unchanged,
        recipe_matches=not mismatches,
        render_exists=render_exists,
        mismatches=mismatches,
        render_path=str(render) if render_exists and render else None,
        render_sha256=render_sha256,
        xmp_present=fixture_xmp.exists(),
        acr_present=acr.exists(),
    )

    result_payload = {
        "schema": "prographer.lightroom-reference-result.v1",
        "verified_at": _utc_now(),
        "exercise_id": manifest["exercise_id"],
        "expected_recipe": manifest["expected_recipe"],
        "expected_lightroom_ui": manifest.get("expected_lightroom_ui"),
        "observed_lightroom_recipe": asdict(observed),
        **asdict(result),
    }

    (workspace_path / "result.json").write_text(
        json.dumps(
            result_payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    manifest["status"] = (
        "verified_pass"
        if result.status == "PASS"
        else "verified_fail"
    )
    manifest["verified_at"] = result_payload["verified_at"]

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return result
