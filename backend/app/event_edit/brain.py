"""v1 event brain: cut the event into moments, pick the anchors the photographer edits, then complete the rest.

Tuned on wedding A (docs/PG_EV_01_EVENT_BRAIN_V1.md), predicting one shooter from the other:
- A moment starts after 20 s without a photo, or when the camera's As Shot jumps more than 15 mired (new light).
- Anchors are the middle photo of the biggest moments; about 4% of the event (120 of ~2,900 photos).
- An edited anchor's exposure and base sliders are copied to its moment, and its white-balance change from As Shot
  (mired, tint) is applied on top of each photo's own As Shot.
- Other photos get the automatic exposure (when available) and keep As Shot; base sliders = the anchors' median.
With 120 anchors: about 50% of the other photos READY (exposure <= 0.15 stop, temperature <= 5 mired, tint <= 2),
about 15% more a small fix. Fully automatic (no anchors): about 15%.
Pure logic: no catalog or file access here.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Callable, Iterable

MOMENT_GAP_SECONDS = 20
LIGHT_JUMP_MIRED = 15.0
ANCHOR_SHARE = 0.04
MIN_ANCHORS, MAX_ANCHORS = 20, 150
BASE_SLIDERS = ("Contrast2012", "Highlights2012", "Shadows2012", "Whites2012", "Blacks2012", "Texture",
                "Clarity2012", "Dehaze", "Vibrance", "Saturation")
TEMPERATURE_RANGE, TINT_RANGE = (2000, 50000), (-150, 150)


@dataclass
class Photo:
    image: int
    seconds: float | None            # capture time in seconds (any fixed origin)
    as_shot_kelvin: float | None
    as_shot_tint: float | None
    develop: dict = field(default_factory=dict)   # current global sliders and "WhiteBalance"
    edited_by_photographer: bool = False


def mired(kelvin: float) -> float:
    return 1e6 / kelvin


def make_moments(photos: Iterable[Photo], gap: float = MOMENT_GAP_SECONDS,
                 light_jump: float = LIGHT_JUMP_MIRED) -> list[list[Photo]]:
    """Consecutive photos form one moment until a pause longer than `gap` or a jump in the camera's As Shot."""
    timed = sorted((p for p in photos if p.seconds is not None), key=lambda p: p.seconds)
    moments: list[list[Photo]] = []
    for p in timed:
        prev = moments[-1][-1] if moments else None
        jump = (prev is not None and p.as_shot_kelvin and prev.as_shot_kelvin
                and abs(mired(p.as_shot_kelvin) - mired(prev.as_shot_kelvin)) > light_jump)
        if prev is None or p.seconds - prev.seconds > gap or jump:
            moments.append([])
        moments[-1].append(p)
    untimed = [p for p in photos if p.seconds is None]
    return moments + [[p] for p in untimed]


def default_anchor_count(photo_count: int) -> int:
    return max(MIN_ANCHORS, min(MAX_ANCHORS, round(ANCHOR_SHARE * photo_count)))


def choose_anchors(moments: list[list[Photo]], count: int) -> list[Photo]:
    """The middle photo of each of the `count` biggest moments (ties: earlier moment first)."""
    order = sorted(range(len(moments)), key=lambda i: (-len(moments[i]), i))
    return [moments[i][len(moments[i]) // 2] for i in order[:count]]


def _white_balance_change(anchor: Photo) -> tuple[float, float] | None:
    """The anchor's white balance as a change from its As Shot, or None when it was left As Shot."""
    d = anchor.develop
    if d.get("WhiteBalance") in (None, "As Shot") or not anchor.as_shot_kelvin or anchor.as_shot_tint is None:
        return None
    if not isinstance(d.get("Temperature"), (int, float)) or not isinstance(d.get("Tint"), (int, float)):
        return None
    return mired(d["Temperature"]) - mired(anchor.as_shot_kelvin), d["Tint"] - anchor.as_shot_tint


def _apply_white_balance(photo: Photo, change: tuple[float, float]) -> dict[str, float] | None:
    if not photo.as_shot_kelvin or photo.as_shot_tint is None:
        return None
    target = mired(photo.as_shot_kelvin) + change[0]
    if target <= 0:
        return None
    kelvin = min(max(1e6 / target, TEMPERATURE_RANGE[0]), TEMPERATURE_RANGE[1])
    tint = min(max(photo.as_shot_tint + change[1], TINT_RANGE[0]), TINT_RANGE[1])
    return {"Temperature": round(kelvin), "Tint": round(tint)}


def event_base(anchors: Iterable[Photo]) -> dict[str, float]:
    """Median of each base slider over the edited anchors (the editor's base for this event)."""
    edited = [a for a in anchors if a.edited_by_photographer]
    out = {}
    for key in BASE_SLIDERS:
        values = [a.develop[key] for a in edited if isinstance(a.develop.get(key), (int, float))]
        if values:
            out[key] = statistics.median(values)
    return out


def complete_event(moments: list[list[Photo]], anchors: list[Photo],
                   auto_exposure: Callable[[Photo], float | None] | None = None) -> dict:
    """Slider values for every photo the photographer did not edit.

    Returns {"edits": {image: {slider: value}}, "summary": {...}}. Photos the photographer edited (including the
    anchors) are never in "edits"."""
    anchor_ids = {a.image for a in anchors}
    edited_anchors = [a for a in anchors if a.edited_by_photographer]
    base = event_base(anchors)
    level = statistics.median(a.develop["Exposure2012"] for a in edited_anchors
                              if isinstance(a.develop.get("Exposure2012"), (int, float))) if edited_anchors else None
    edits: dict[int, dict] = {}
    counts = {"from_anchor": 0, "automatic": 0, "event_level": 0, "skipped_edited": 0, "no_exposure": 0}
    for moment in moments:
        anchor = next((p for p in moment if p.image in anchor_ids and p.edited_by_photographer), None)
        wb_change = _white_balance_change(anchor) if anchor else None
        for photo in moment:
            if photo.edited_by_photographer:
                counts["skipped_edited"] += 1
                continue
            values: dict[str, float] = {}
            if anchor is not None:
                values.update({k: anchor.develop[k] for k in BASE_SLIDERS if isinstance(anchor.develop.get(k), (int, float))})
                if isinstance(anchor.develop.get("Exposure2012"), (int, float)):
                    values["Exposure2012"] = anchor.develop["Exposure2012"]
                if wb_change is not None:
                    values.update(_apply_white_balance(photo, wb_change) or {})
                counts["from_anchor"] += 1
            else:
                values.update(base)
                exposure = auto_exposure(photo) if auto_exposure else None
                if exposure is not None:
                    values["Exposure2012"] = exposure
                    counts["automatic"] += 1
                elif level is not None:
                    values["Exposure2012"] = level
                    counts["event_level"] += 1
                else:
                    counts["no_exposure"] += 1
            if "Exposure2012" in values:
                values["Exposure2012"] = round(min(max(values["Exposure2012"], -5.0), 5.0), 2)
            if values:
                edits[photo.image] = values
    summary = {"photos": sum(len(m) for m in moments), "moments": len(moments), "anchors": len(anchors),
               "anchors_edited": len(edited_anchors), **counts}
    return {"edits": edits, "summary": summary}
