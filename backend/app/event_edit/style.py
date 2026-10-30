"""The editing style a learning profile carries into a new event (automatic editing, as Imagen does).

Learnt from the profile's catalogs (before/after pairs, PG-LI-04) and stored with the profile as numbers only:
- base sliders: the median of each base slider over the editor's photos (Contrast, Highlights, Shadows, Whites,
  Blacks, Texture, Clarity, Dehaze, Vibrance, Saturation);
- exposure: the "target" method (exposure_target.py): the face lightness the editor ends at and how much more
  exposure darker faces get, plus the median exposure as a fallback for events without faces/Smart Previews;
- white balance: As Shot. On wedding A no rule from camera data beat As Shot (53-66% within limits), and aiming at a
  face colour was worse, so the camera's white balance is kept.
Photos the editor turned black & white are left out: their sliders (contrast, clarity, saturation, exposure) serve a
monochrome look and would pull the colour style of every event photo towards it. Which photos to turn black & white
is a separate decision, not learnt yet.
Evidence and limits: docs/PG_EV_01_EVENT_BRAIN_V1.md. Learnt from one wedding so far: expect about 15% of photos
exactly as the editor would leave them and about 25% more within a small fix; more edited events will improve it.
"""
from __future__ import annotations

import statistics
from typing import Any, Callable

from app.event_edit.brain import BASE_SLIDERS

STYLE_VERSION = 2  # 2: black & white photos left out of the colour style
MAX_FACE_SAMPLES = 400


def learn(pairs: list[dict[str, Any]], measure: Callable[[Any], dict | None] | None, curve: dict | None,
          progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    """pairs: [{"dng": path, "targets": {slider: value}}] from build_pairs; measure(dng) -> face measurement."""
    from app.event_edit import exposure_target as et

    every = len(pairs)
    pairs = [p for p in pairs if not (p.get("other_edits") or {}).get("black_and_white")]
    base = {}
    for key in BASE_SLIDERS:
        values = [p["targets"][key] for p in pairs if isinstance(p["targets"].get(key), (int, float))]
        if values:
            base[key] = statistics.median(values)
    exposures = [p["targets"]["Exposure2012"] for p in pairs if "Exposure2012" in p["targets"]]
    style: dict[str, Any] = {"version": STYLE_VERSION, "photos": len(pairs),
                             "black_and_white_excluded": every - len(pairs), "base": base,
                             "exposure_level": statistics.median(exposures) if exposures else 0.0,
                             "exposure_style": None, "faces": 0, "white_balance": "as_shot"}
    if measure is None or curve is None:
        return style
    with_exposure = [p for p in pairs if "Exposure2012" in p["targets"]]
    sample = with_exposure[::max(1, len(with_exposure) // MAX_FACE_SAMPLES)][:MAX_FACE_SAMPLES]
    faces = []
    for n, pair in enumerate(sample, start=1):
        m = measure(pair["dng"])
        if m and m.get("face_rgb") is not None:
            faces.append({**m, "exposure": pair["targets"]["Exposure2012"]})
        if progress and (n % 10 == 0 or n == len(sample)):
            progress(n, len(sample))
    learnt = et.learn_style(faces, curve)
    style["faces"] = len(faces)
    if learnt is not None:
        style["exposure_style"] = {"target_face_lightness": learnt.target_face_lightness, "slope": learnt.slope}
    return style
