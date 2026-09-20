from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    import rawpy  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    rawpy = None

from .recipes import RECIPE_CONTRACT_VERSION, canonicalize_recipe


DARKROOM_PREVIEW_FORMAT = "prographer-production-darkroom-preview-v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_production_darkroom_schema(conn: sqlite3.Connection) -> None:
    """
    Additive Stage 4 migration.
    Existing renders/feedback/events/training data are not changed.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS photo_ai_preview_renders (
            id TEXT PRIMARY KEY,
            photo_id TEXT NOT NULL,
            prediction_id TEXT NOT NULL,
            profile_version_id TEXT NOT NULL,
            recipe_contract_version TEXT NOT NULL,
            process_family TEXT NOT NULL DEFAULT 'unknown',
            recipe_hash TEXT NOT NULL,
            recipe_json TEXT NOT NULL,
            rendered_path TEXT NOT NULL,
            width INTEGER,
            height INTEGER,
            preview_format TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(photo_id, prediction_id, recipe_hash),
            FOREIGN KEY(photo_id) REFERENCES photos(id) ON DELETE CASCADE,
            FOREIGN KEY(prediction_id) REFERENCES photo_ai_predictions(id) ON DELETE CASCADE,
            FOREIGN KEY(profile_version_id) REFERENCES ai_profile_versions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_photo_ai_preview_renders_photo
            ON photo_ai_preview_renders(photo_id, created_at DESC);
        """
    )


def infer_process_family(
    recipe: dict[str, Any],
    explicit: Optional[str] = None,
) -> str:
    explicit = str(explicit or "").strip().lower()
    if explicit in {"legacy", "modern"}:
        return explicit

    # Lightroom legacy controls are unambiguous markers.
    if any(key in recipe for key in ("brightness", "recovery", "fill_light")):
        return "legacy"
    return "modern"


def recipe_neutral_value(key: str, process_family: str) -> float:
    if process_family == "legacy":
        legacy = {
            "contrast": 25.0,
            "blacks": 5.0,
            "brightness": 50.0,
        }
        if key in legacy:
            return legacy[key]
    return 0.0


def canonical_recipe_hash(recipe: dict[str, Any]) -> str:
    clean = canonicalize_recipe(recipe)
    raw = json.dumps(
        clean,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def render_row_public(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    try:
        item["recipe"] = json.loads(item.pop("recipe_json"))
    except Exception:
        item["recipe"] = {}
    return item


def latest_ai_preview_render(
    conn: sqlite3.Connection,
    *,
    photo_id: str,
    prediction_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if prediction_id:
        row = conn.execute(
            """
            SELECT *
            FROM photo_ai_preview_renders
            WHERE photo_id=? AND prediction_id=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (photo_id, prediction_id),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT *
            FROM photo_ai_preview_renders
            WHERE photo_id=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (photo_id,),
        ).fetchone()
    return render_row_public(row) if row else None


def _clamp_channel(v: float) -> int:
    return max(0, min(255, int(round(v))))


def _apply_temperature_kelvin(img: Image.Image, kelvin: float) -> Image.Image:
    """
    Preview-only approximation.

    The website preview is already camera-rendered, so this cannot reproduce
    Lightroom RAW white balance exactly. The canonical Kelvin value stays
    untouched; only this temporary JPEG preview is approximated.
    """
    kelvin = max(2000.0, min(50000.0, float(kelvin)))
    if abs(kelvin - 5000.0) < 1.0:
        return img

    strength = max(-100.0, min(100.0, math.log2(kelvin / 5000.0) * 62.0))
    red_mult = max(0.68, min(1.32, 1.0 + strength / 310.0))
    blue_mult = max(0.68, min(1.32, 1.0 - strength / 310.0))

    r, g, b = img.split()
    r = r.point(lambda x: _clamp_channel(x * red_mult))
    b = b.point(lambda x: _clamp_channel(x * blue_mult))
    return Image.merge("RGB", (r, g, b))


def _apply_tint(img: Image.Image, tint: float) -> Image.Image:
    tint = max(-150.0, min(150.0, float(tint)))
    if abs(tint) < 0.001:
        return img

    # Positive tint = magenta, negative tint = green.
    shift = tint / 450.0
    r_mult = max(0.78, min(1.22, 1.0 + shift * 0.35))
    b_mult = max(0.78, min(1.22, 1.0 + shift * 0.35))
    g_mult = max(0.72, min(1.28, 1.0 - shift))

    r, g, b = img.split()
    r = r.point(lambda x: _clamp_channel(x * r_mult))
    g = g.point(lambda x: _clamp_channel(x * g_mult))
    b = b.point(lambda x: _clamp_channel(x * b_mult))
    return Image.merge("RGB", (r, g, b))


def _apply_local_tone(
    img: Image.Image,
    *,
    shadows: float = 0.0,
    highlights: float = 0.0,
    blacks_delta: float = 0.0,
    whites: float = 0.0,
) -> Image.Image:
    gray = ImageOps.grayscale(img)

    if abs(shadows) > 0.001:
        mask = gray.point(
            lambda p: int(((255 - p) / 255.0) ** 1.4 * min(abs(shadows), 100))
        )
        adjusted = ImageEnhance.Brightness(img).enhance(
            max(0.35, 1.0 + shadows / 125.0)
        )
        img = Image.composite(adjusted, img, mask)

    if abs(highlights) > 0.001:
        mask = gray.point(
            lambda p: int((p / 255.0) ** 1.5 * min(abs(highlights), 100))
        )
        adjusted = ImageEnhance.Brightness(img).enhance(
            max(0.35, 1.0 + highlights / 145.0)
        )
        img = Image.composite(adjusted, img, mask)

    if abs(blacks_delta) > 0.001:
        mask = gray.point(
            lambda p: int(((255 - p) / 255.0) ** 2.2 * min(abs(blacks_delta), 100))
        )
        adjusted = ImageEnhance.Contrast(img).enhance(
            max(0.4, 1.0 + blacks_delta / 100.0)
        )
        img = Image.composite(adjusted, img, mask)

    if abs(whites) > 0.001:
        mask = gray.point(
            lambda p: int((p / 255.0) ** 2.2 * min(abs(whites), 100))
        )
        adjusted = ImageEnhance.Contrast(img).enhance(
            max(0.4, 1.0 + whites / 110.0)
        )
        img = Image.composite(adjusted, img, mask)

    return img


def _develop_raw_base(
    source_path: Path,
    *,
    exposure_stops: float,
) -> Image.Image:
    if rawpy is None:
        raise RuntimeError(
            "RAW preview requires rawpy. Install RAW support before editing."
        )

    # Apply exposure during RAW development, not after the file has already been
    # converted to JPEG. This prevents the Stage-4 double-development failure.
    exposure_stops = max(-3.0, min(3.0, float(exposure_stops)))
    bright = max(0.125, min(8.0, 2.0 ** exposure_stops))

    with rawpy.imread(str(source_path)) as raw:
        kwargs = {
            "use_camera_wb": True,
            "no_auto_bright": True,
            "half_size": True,
            "output_bps": 8,
            "bright": bright,
        }
        try:
            kwargs["highlight_mode"] = rawpy.HighlightMode.Blend
        except Exception:
            pass
        rgb = raw.postprocess(**kwargs)

    image = Image.fromarray(rgb).convert("RGB")
    image.thumbnail((2200, 2200))
    return image


def render_production_recipe_preview(
    source_path: Path,
    recipe: dict[str, Any],
    destination: Path,
    *,
    process_family: str = "unknown",
    source_is_raw: bool = False,
) -> tuple[int, int, dict[str, float], str]:
    """
    Local preview renderer for the canonical Production Recipe.

    RAW events are developed ONCE from the original RAW. Exposure is applied
    inside rawpy development. Remaining controls are conservative preview
    approximations. Lightroom/XMP remains the authoritative final render.
    """
    clean = canonicalize_recipe(recipe)
    family = infer_process_family(clean, process_family)

    if not source_is_raw:
        raise RuntimeError(
            "Production Darkroom preview is RAW-only in ProGrapher V1."
        )

    exposure = float(clean.get("exposure", 0.0))
    img = _develop_raw_base(
        Path(source_path),
        exposure_stops=exposure,
    )

    # Do NOT apply Exposure again here. It already happened during RAW development.

    contrast = float(
        clean.get("contrast", recipe_neutral_value("contrast", family))
    )
    contrast_delta = contrast - recipe_neutral_value("contrast", family)
    if abs(contrast_delta) > 0.001:
        # More conservative than the old JPEG renderer.
        img = ImageEnhance.Contrast(img).enhance(
            max(0.55, min(1.65, 1.0 + contrast_delta / 160.0))
        )

    if "brightness" in clean:
        brightness = float(clean["brightness"])
        brightness_delta = brightness - recipe_neutral_value("brightness", family)
        if abs(brightness_delta) > 0.001:
            img = ImageEnhance.Brightness(img).enhance(
                max(0.72, min(1.35, 1.0 + brightness_delta / 260.0))
            )

    # Kelvin/Tint are still preview approximations because rawpy does not expose
    # Lightroom's camera-profile WB conversion. Keep the effect intentionally mild.
    if "temperature" in clean:
        img = _apply_temperature_kelvin(img, float(clean["temperature"]))
    if "tint" in clean:
        img = _apply_tint(img, float(clean["tint"]))

    vibrance = float(clean.get("vibrance", 0.0))
    if abs(vibrance) > 0.001:
        img = ImageEnhance.Color(img).enhance(
            max(0.65, min(1.55, 1.0 + vibrance / 220.0))
        )

    saturation = float(clean.get("saturation", 0.0))
    if abs(saturation) > 0.001:
        img = ImageEnhance.Color(img).enhance(
            max(0.60, min(1.60, 1.0 + saturation / 180.0))
        )

    shadows = float(clean.get("shadows", 0.0))
    highlights = float(clean.get("highlights", 0.0))
    whites = float(clean.get("whites", 0.0))
    blacks = float(
        clean.get("blacks", recipe_neutral_value("blacks", family))
    )
    blacks_delta = blacks - recipe_neutral_value("blacks", family)

    if "fill_light" in clean:
        shadows += float(clean["fill_light"]) * 0.35
    if "recovery" in clean:
        highlights -= float(clean["recovery"]) * 0.40

    img = _apply_local_tone(
        img,
        shadows=max(-60.0, min(60.0, shadows)),
        highlights=max(-60.0, min(60.0, highlights)),
        blacks_delta=max(-45.0, min(45.0, blacks_delta)),
        whites=max(-45.0, min(45.0, whites)),
    )

    clarity = float(clean.get("clarity", 0.0))
    if clarity > 0:
        img = img.filter(
            ImageFilter.UnsharpMask(
                radius=1.25,
                percent=min(120, int(clarity * 1.25)),
                threshold=3,
            )
        )
    elif clarity < 0:
        img = img.filter(
            ImageFilter.GaussianBlur(radius=min(1.0, abs(clarity) / 55.0))
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    img.save(destination, format="JPEG", quality=94, optimize=True)
    return img.size[0], img.size[1], clean, family


def save_prediction_preview_render(
    conn: sqlite3.Connection,
    *,
    photo_id: str,
    prediction: dict[str, Any],
    rendered_path: str,
    width: int,
    height: int,
    process_family: str,
) -> dict[str, Any]:
    recipe = prediction.get("recipe") or {}
    recipe_hash = canonical_recipe_hash(recipe)

    existing = conn.execute(
        """
        SELECT *
        FROM photo_ai_preview_renders
        WHERE photo_id=? AND prediction_id=? AND recipe_hash=?
        LIMIT 1
        """,
        (photo_id, prediction["id"], recipe_hash),
    ).fetchone()
    if existing:
        return render_row_public(existing)

    render_id = str(uuid.uuid4())
    created_at = _utc_now()
    conn.execute(
        """
        INSERT INTO photo_ai_preview_renders (
            id,photo_id,prediction_id,profile_version_id,
            recipe_contract_version,process_family,recipe_hash,recipe_json,
            rendered_path,width,height,preview_format,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            render_id,
            photo_id,
            prediction["id"],
            prediction["profile_version_id"],
            prediction.get("recipe_contract_version") or RECIPE_CONTRACT_VERSION,
            process_family,
            recipe_hash,
            json.dumps(canonicalize_recipe(recipe), ensure_ascii=False),
            rendered_path,
            int(width),
            int(height),
            DARKROOM_PREVIEW_FORMAT,
            created_at,
        ),
    )
    row = conn.execute(
        "SELECT * FROM photo_ai_preview_renders WHERE id=?",
        (render_id,),
    ).fetchone()
    return render_row_public(row)
