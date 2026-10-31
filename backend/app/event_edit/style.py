"""The editing style a learning profile carries into a new event (automatic editing, as Imagen does).

Learnt from the profile's catalogs (before/after pairs, PG-LI-04) and stored with the profile as numbers only:
- base sliders: the median of each base slider over the editor's photos (Contrast, Highlights, Shadows, Whites,
  Blacks, Texture, Clarity, Dehaze, Vibrance, Saturation);
- exposure: the "target" method (exposure_target.py): the face lightness the editor ends at and how much more
  exposure darker faces get, plus the median exposure as a fallback for events without faces/Smart Previews;
- exposure correction by flash: what the editor did differently from the face method on photos with and without
  flash (on wedding A the face method left flash photos about 0.12 stop too dark and the others 0.15 too bright);
- white balance: As Shot, except in a kind of light (the camera's As Shot temperature, with or without flash) where the
  editor nearly always moved it the same way (at least 75% of 20+ photos): there it is moved by his median change.
  On wedding A that is warm light (3,800-4,600 K), cooled by about 13 mired without flash and 32 with. A rule for
  every kind of light was worse than As Shot, because the editor left half the photos As Shot.
These two rules took wedding A from 12.7% to 16.1% of photos exactly as the editor (37% to 46% within a small fix),
learnt on half of the hours and scored on the other half (camera_test_kit/rule_simulation.py).
A slider the editor set on fewer than half of the photos is not part of the style (it stays as Lightroom left it).
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

STYLE_VERSION = 4  # 2: black & white left out; 3: rarely used sliders left out; 4: flash and white-balance rules
# A base slider is part of the style only if the editor set it on at least this share of the photos (Dehaze on 1 photo
# of 3,184 must not reach every photo of an event); as the profile page's "rare" sliders.
MIN_SHARE_PRESENT = 0.5
MAX_FACE_SAMPLES = 400
MIN_RULE_PHOTOS = 20        # a flash or light group needs this many photos to get a rule
WB_NEARLY_ALWAYS = 0.75     # share of a light group the editor must have moved for a white-balance rule
WB_CHANGED_MIRED = 5.0      # a move smaller than this is "left As Shot" (the research limit)
K_BINS = ((0, 3800), (3800, 4600), (4600, 5400), (5400, 6200), (6200, 100000))


def kelvin_bin(kelvin: float) -> tuple[int, int] | None:
    return next(((lo, hi) for lo, hi in K_BINS if lo <= kelvin < hi), None)


def flash_key(flash: bool | None) -> str | None:
    return None if flash is None else "flash" if flash else "no_flash"


def white_balance_rules(pairs: list[dict[str, Any]], as_shot: Callable[[Any], tuple[float, float] | None]
                        ) -> list[dict[str, Any]]:
    """Kinds of light where the editor nearly always moved the camera's As Shot the same way (mired: + = bluer)."""
    groups: dict[tuple, list[float]] = {}
    for pair in pairs:
        targets, flash = pair["targets"], flash_key(pair.get("flash"))
        if flash is None:
            continue
        shot = as_shot(pair["dng"])
        if not shot or not shot[0] or shot[0] <= 0:
            continue
        if pair.get("white_balance") == "As Shot":
            move = 0.0
        elif isinstance(targets.get("Temperature"), (int, float)) and targets["Temperature"] > 0:
            move = 1e6 / targets["Temperature"] - 1e6 / shot[0]
        else:
            continue
        light = kelvin_bin(shot[0])
        if light:
            groups.setdefault((light, flash), []).append(move)
    rules = []
    for (light, flash), moves in sorted(groups.items()):
        changed = [m for m in moves if abs(m) > WB_CHANGED_MIRED]
        if len(moves) >= MIN_RULE_PHOTOS and len(changed) >= WB_NEARLY_ALWAYS * len(moves):
            rules.append({"kelvin_min": light[0], "kelvin_max": light[1], "flash": flash,
                          "mired": round(statistics.median(changed), 1), "photos": len(moves)})
    return rules


def exposure_flash_offsets(faces: list[dict[str, Any]], learnt, curve: dict) -> dict[str, float]:
    """What the editor did on top of the face method, separately for photos with and without flash. Each event day
    is solved on its own, as a new event would be."""
    from app.event_edit import exposure_target as et

    residuals: dict[str, list[float]] = {}
    days: dict[Any, list[dict]] = {}
    for face in faces:
        days.setdefault(face.get("day"), []).append(face)
    for day_faces in days.values():
        predicted = et.automatic_exposures(dict(enumerate(day_faces)), learnt, curve)
        for i, face in enumerate(day_faces):
            key = flash_key(face.get("flash"))
            if key and i in predicted:
                residuals.setdefault(key, []).append(face["exposure"] - predicted[i])
    return {key: round(statistics.median(values), 2) for key, values in sorted(residuals.items())
            if len(values) >= MIN_RULE_PHOTOS}


def learn(pairs: list[dict[str, Any]], measure: Callable[[Any], dict | None] | None, curve: dict | None,
          progress: Callable[[int, int], None] | None = None,
          as_shot: Callable[[Any], tuple[float, float] | None] | None = None) -> dict[str, Any]:
    """pairs: [{"dng": path, "targets": {slider: value}, "flash", "white_balance", "capture_day"}] from build_pairs;
    measure(dng) -> face measurement; as_shot(dng) -> the camera's (Kelvin, tint)."""
    from app.event_edit import exposure_target as et

    every = len(pairs)
    pairs = [p for p in pairs if not (p.get("other_edits") or {}).get("black_and_white")]
    base = {}
    for key in BASE_SLIDERS:
        values = [p["targets"][key] for p in pairs if isinstance(p["targets"].get(key), (int, float))]
        if values and len(values) >= MIN_SHARE_PRESENT * len(pairs):  # a slider the editor rarely touches stays off
            base[key] = statistics.median(values)
    exposures = [p["targets"]["Exposure2012"] for p in pairs if "Exposure2012" in p["targets"]]
    style: dict[str, Any] = {"version": STYLE_VERSION, "photos": len(pairs),
                             "black_and_white_excluded": every - len(pairs), "base": base,
                             "exposure_level": statistics.median(exposures) if exposures else 0.0,
                             "exposure_style": None, "faces": 0, "white_balance": "as_shot",
                             "white_balance_rules": white_balance_rules(pairs, as_shot) if as_shot else [],
                             "exposure_flash_offsets": {}}
    if measure is None or curve is None:
        return style
    with_exposure = [p for p in pairs if "Exposure2012" in p["targets"]]
    sample = with_exposure[::max(1, len(with_exposure) // MAX_FACE_SAMPLES)][:MAX_FACE_SAMPLES]
    faces = []
    for n, pair in enumerate(sample, start=1):
        m = measure(pair["dng"])
        if m and m.get("face_rgb") is not None:
            faces.append({**m, "exposure": pair["targets"]["Exposure2012"], "flash": pair.get("flash"),
                          "day": pair.get("capture_day")})
        if progress and (n % 10 == 0 or n == len(sample)):
            progress(n, len(sample))
    learnt = et.learn_style(faces, curve)
    style["faces"] = len(faces)
    if learnt is not None:
        style["exposure_style"] = {"target_face_lightness": learnt.target_face_lightness, "slope": learnt.slope}
        style["exposure_flash_offsets"] = exposure_flash_offsets(faces, learnt, curve)
    return style
