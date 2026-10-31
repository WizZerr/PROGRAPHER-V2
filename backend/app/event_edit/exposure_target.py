"""Automatic exposure, "target" method: the editor brings faces to about the same final brightness for every shooter.

Learnt from a past event: the face lightness (L*) the editor ends at, and how much more exposure darker faces get
(the slope, about -0.17 to -0.19 stop per stop of face brightness on wedding A). For a new event the exposure LEVEL
is solved so that the median face lands on that lightness; each photo then gets level + slope x (its face - median).
On wedding A, predicting each shooter from the other without any of its edits: level within 0.04 / 0.15 stop of the
editor's, per-photo error 0.25-0.27 stop (docs/PG_EV_01_EVENT_BRAIN_V1.md).

"Before" colours come from the Smart Preview rendered like Lightroom Reset (vendored smart_preview_decoder), stopped
before the tone curve. Faces are found with OpenCV's YuNet model; without it the automatic exposure is off (callers
fall back to the anchors' level). Nothing is written to disk.
"""
from __future__ import annotations

import os
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.platform.paths import user_data_dir

FACE_MODEL_ENV = "PROGRAPHER_FACE_MODEL"
FACE_MODEL_NAME = "face_detection_yunet_2023mar.onnx"
LUMA = np.array([0.2126, 0.7152, 0.0722])


@dataclass(frozen=True)
class ExposureStyle:
    target_face_lightness: float   # L* of faces after the editor's exposure (Lightroom-like render)
    slope: float                   # exposure change per stop of face brightness (negative: darker faces get more)


def face_lightness(face_rgb: np.ndarray, exposure: float, curve: dict) -> float:
    """L* of a face colour (linear sRGB at exposure 0) after exposure and the Lightroom-like tone curve."""
    lin = np.maximum(np.asarray(face_rgb, dtype=float) * 2.0 ** exposure, 2 ** -14)
    v = np.clip(np.interp(np.log2(lin), curve["x"], curve["y"]), 0, 1)
    y = float(np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4) @ LUMA)
    return 116 * np.cbrt(y) - 16 if y > 0.008856 else 903.3 * y


def fit_slope(face_stops: list[float], exposures: list[float], pairs: int = 4000) -> float:
    """Robust slope of exposure against face brightness (Theil-Sen on random pairs)."""
    pts = list(zip(face_stops, exposures))
    if len(pts) < 10:
        return 0.0
    idx = np.random.default_rng(0).integers(0, len(pts), size=(pairs, 2))
    slopes = [(pts[j][1] - pts[i][1]) / (pts[j][0] - pts[i][0]) for i, j in idx if abs(pts[j][0] - pts[i][0]) > 0.1]
    return float(np.median(slopes)) if slopes else 0.0


def learn_style(faces: list[dict], curve: dict) -> ExposureStyle | None:
    """From photos of an edited event: [{"face_rgb", "face_stops", "exposure"}]."""
    faces = [f for f in faces if f.get("face_rgb") is not None]
    if len(faces) < 20:
        return None
    target = statistics.median(face_lightness(f["face_rgb"], f["exposure"], curve) for f in faces)
    return ExposureStyle(float(target), fit_slope([f["face_stops"] for f in faces], [f["exposure"] for f in faces]))


def solve_level(faces: list[dict], style: ExposureStyle, curve: dict) -> tuple[float, float] | None:
    """(level, median face stops) so the event's median face reaches the style's lightness."""
    faces = [f for f in faces if f.get("face_rgb") is not None]
    if len(faces) < 5:
        return None
    mid = statistics.median(f["face_stops"] for f in faces)
    rules = [style.slope * (f["face_stops"] - mid) for f in faces]
    lo, hi = -3.0, 3.0
    for _ in range(40):
        level = (lo + hi) / 2
        med = statistics.median(face_lightness(f["face_rgb"], level + r, curve) for f, r in zip(faces, rules))
        lo, hi = (level, hi) if med < style.target_face_lightness else (lo, level)
    return (lo + hi) / 2, mid


def automatic_exposures(measured: dict[int, dict], style: ExposureStyle, curve: dict) -> dict[int, float]:
    """Exposure per photo: level + slope x (face - median); photos without a face get the level."""
    solved = solve_level(list(measured.values()), style, curve)
    if solved is None:
        return {}
    level, mid = solved
    return {image: level + (style.slope * (m["face_stops"] - mid) if m.get("face_rgb") is not None else 0.0)
            for image, m in measured.items()}


# --- measuring a Smart Preview -----------------------------------------------------------------------------------

def face_model_path() -> Path | None:
    for path in (os.getenv(FACE_MODEL_ENV), user_data_dir() / "models" / FACE_MODEL_NAME):
        if path and Path(path).is_file():
            return Path(path)
    return None


def load_face_detector():
    """YuNet face detector, or None when OpenCV or the model file is missing."""
    path = face_model_path()
    if path is None:
        return None
    try:
        import cv2

        return cv2.FaceDetectorYN.create(str(path), "", (320, 320), 0.8, 0.3, 5000)
    except Exception:  # noqa: BLE001  (no usable OpenCV build: automatic exposure stays off)
        return None


def _largest_face(detector, rgb_u8: np.ndarray):
    import cv2

    bgr = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2BGR)
    detector.setInputSize((bgr.shape[1], bgr.shape[0]))
    _, found = detector.detect(bgr)
    boxes = [] if found is None else [tuple(int(v) for v in f[:4]) for f in found]
    boxes = [(max(x, 0), max(y, 0), w, h) for x, y, w, h in boxes if w > 8 and h > 8]
    return max(boxes, key=lambda b: b[2] * b[3]) if boxes else None


def linear_before(decoder, sp, look) -> np.ndarray:
    """Linear sRGB of the Lightroom-Reset render, before the tone curve (same steps as decoder.render_srgb)."""
    from smart_preview_decoder.profile import PROPHOTO_TO_SRGB, apply_hsv_table

    curve = decoder.load_tone_curve()
    prof = decoder.EmbeddedProfile(sp.tags)
    w = prof.weight(sp.as_shot_neutral)
    x = np.clip(sp.linear.astype(np.float64) / sp.as_shot_neutral, 0, 1)
    pp = np.clip(x @ prof.camera_to_prophoto(w).T, 0, None)
    hsm = prof.hue_sat_map(w)
    if hsm is not None and prof.hsm_dims is not None:
        pp = apply_hsv_table(pp, prof.hsm_dims, hsm, prof.hsm_srgb)
    if prof.lut is not None and prof.lut_dims is not None and not (look is not None and curve["look_mode"] == "replace"):
        pp = apply_hsv_table(pp, prof.lut_dims, prof.lut, prof.lut_srgb)
    if look is not None:
        pp = apply_hsv_table(pp, look[0], look[1], curve["look_srgb"])
    return np.clip(pp @ PROPHOTO_TO_SRGB.T, 0, None) * 2.0 ** (sp.baseline_exposure + prof.exp_offset
                                                                 + decoder.CALIBRATION_STOPS)


def measure_face(decoder, sp, look, detector, curve: dict) -> dict[str, Any]:
    """{"face_rgb", "face_stops"} of the largest face, or {} when none is found."""
    lin = linear_before(decoder, sp, look)
    boost = float(np.clip(np.log2(0.18 / max(float(np.median(lin @ LUMA)), 1e-6)), 0, 3))  # only to find faces
    shown = np.clip(np.interp(np.log2(np.maximum(lin * 2.0 ** boost, 2 ** -14)), curve["x"], curve["y"]), 0, 1)
    face = _largest_face(detector, (shown * 255).astype(np.uint8))
    if not face:
        return {}
    x, y, w, h = face
    core = lin[y + h // 5: y + 4 * h // 5, x + w // 5: x + 4 * w // 5].reshape(-1, 3)
    if not len(core):
        return {}
    rgb = core.mean(axis=0)
    return {"face_rgb": rgb, "face_stops": float(np.log2(max(float(rgb @ LUMA), 1e-6)))}


def face_measurer(long_edge: int = 640):
    """(measure(dng_path) -> {"face_rgb", "face_stops"} | {} | None, curve, reason). measure is None (with a reason)
    when the face model, OpenCV or the Smart Preview decoder is unavailable; a photo that cannot be read gives None."""
    detector = load_face_detector()
    if detector is None:
        return None, None, "face_model_missing"
    try:
        from app.learning_intake.decoder_vendor import load_decoder_package
        from app.learning_intake.smart_preview_render import find_adobe_color_look

        decoder = load_decoder_package()
    except Exception:  # noqa: BLE001
        return None, None, "decoder_unavailable"
    look, curve = find_adobe_color_look(decoder), decoder.load_tone_curve()

    def measure(path) -> dict | None:
        try:
            return measure_face(decoder, decoder.decode_smart_preview(path, long_edge=long_edge), look, detector, curve)
        except Exception:  # noqa: BLE001  (one unreadable Smart Preview must not stop the rest)
            return None
    return measure, curve, None
