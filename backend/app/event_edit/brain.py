"""v1 event brain: cut the event into moments, pick the anchors the photographer edits, then complete the rest.

Tuned on wedding A (docs/PG_EV_01_EVENT_BRAIN_V1.md), predicting one shooter from the other:
- A moment starts after 20 s without a photo, or when the camera's As Shot jumps more than 15 mired (new light).
- Anchors are the middle photo of the biggest moments; about 4% of the event (120 of ~2,900 photos).
- An edited anchor's exposure and base sliders are copied to its moment, and its white-balance change from As Shot
  (mired, tint) is applied on top of each photo's own As Shot.
- With 120 anchors: about 50% of the other photos READY (exposure <= 0.15 stop, temperature <= 5 mired, tint <= 2),
  about 15% more a small fix. Without an anchor in the moment the evidence is weak: automatic exposure alone was
  within 0.15 stop on only 24-27% of photos (about 15% READY), so those photos are SKIPPED by default.

Gates (assess_anchors / complete_event), each tied to the evidence above:
- MIN_EDITED_ANCHORS = 20: the smallest anchor count evaluated in the tuning; below it there is no evidence at all
  for the event as a whole, so completion is refused (or, for a small event, every planned anchor must be edited).
- A photo is written only from an edited anchor of its own moment (the measured "anchor copy" case).
- ...and only if its camera As Shot is within LIGHT_JUMP_MIRED (15) of the anchor's: the same threshold that splits
  moments; beyond it the light changed and the anchor is not evidence for that photo.
- If the anchor changed white balance but the photo's As Shot is unknown, the photo is skipped (no blind change).
Everything skipped is reported with its reason. Pure logic: no catalog or file access here.
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
MIN_EDITED_ANCHORS = 20
# camera As Shot bins (Kelvin) used to report light coverage, as in the white-balance pattern research
LIGHT_BINS = (0, 3200, 3800, 4400, 5000, 5600, 6400, 10**6)


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


def light_bin(kelvin: float | None) -> str:
    if not kelvin:
        return "unknown"
    for lo, hi in zip(LIGHT_BINS, LIGHT_BINS[1:]):
        if lo <= kelvin < hi:
            return f"{lo}-{hi if hi < 10**6 else ''}K"
    return "unknown"


def assess_anchors(moments: list[list[Photo]], anchors: list[Photo]) -> dict:
    """Is there enough evidence to complete the event? Coverage by moments and by light, plus the blocking gate."""
    photos = [p for m in moments for p in m]
    anchor_ids = {a.image for a in anchors}
    edited_ids = {a.image for a in anchors if a.edited_by_photographer}
    covered_moments = [m for m in moments if any(p.image in edited_ids for p in m)]
    covered = sum(len(m) for m in covered_moments)
    light: dict[str, dict[str, int]] = {}
    for m in moments:
        has_anchor = any(p.image in edited_ids for p in m)
        for p in m:
            b = light.setdefault(light_bin(p.as_shot_kelvin), {"photos": 0, "covered": 0})
            b["photos"] += 1
            b["covered"] += has_anchor
    required = min(MIN_EDITED_ANCHORS, len(anchor_ids)) if anchor_ids else MIN_EDITED_ANCHORS
    blocking = []
    if len(edited_ids) < required:
        blocking.append({"reason": "too_few_edited_anchors", "edited": len(edited_ids), "required": required})
    uncovered_light = sorted(k for k, v in light.items() if v["covered"] == 0 and k != "unknown")
    return {"photos": len(photos), "moments": len(moments), "anchors_planned": len(anchor_ids),
            "anchors_edited": len(edited_ids), "required_edited": required,
            "moments_with_edited_anchor": len(covered_moments), "photos_in_covered_moments": covered,
            "covered_share": round(covered / len(photos), 3) if photos else 0.0,
            "light_bins": light, "light_bins_without_example": uncovered_light,
            "blocking": blocking, "ok": not blocking}


def complete_event(moments: list[list[Photo]], anchors: list[Photo],
                   auto_exposure: Callable[[Photo], float | None] | None = None, *,
                   fill_unanchored: bool = False) -> dict:
    """Slider values for the photos ProGrapher has evidence for.

    Returns {"edits": {image: {slider: value}}, "skipped": {image: reason}, "summary": {...}}. Photos the
    photographer edited (including the anchors) are never in "edits". fill_unanchored=True also fills moments
    without an edited anchor (automatic exposure or the anchors' median) - weak evidence, off by default."""
    anchor_ids = {a.image for a in anchors}
    edited_anchors = [a for a in anchors if a.edited_by_photographer]
    base = event_base(anchors)
    level = statistics.median(a.develop["Exposure2012"] for a in edited_anchors
                              if isinstance(a.develop.get("Exposure2012"), (int, float))) if edited_anchors else None
    edits: dict[int, dict] = {}
    skipped: dict[int, str] = {}
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
                if (photo.as_shot_kelvin and anchor.as_shot_kelvin and
                        abs(mired(photo.as_shot_kelvin) - mired(anchor.as_shot_kelvin)) > LIGHT_JUMP_MIRED):
                    skipped[photo.image] = "light_differs_from_anchor"
                    continue
                if wb_change is not None and (not photo.as_shot_kelvin or photo.as_shot_tint is None):
                    skipped[photo.image] = "white_balance_unknown"
                    continue
                values.update({k: anchor.develop[k] for k in BASE_SLIDERS if isinstance(anchor.develop.get(k), (int, float))})
                if isinstance(anchor.develop.get("Exposure2012"), (int, float)):
                    values["Exposure2012"] = anchor.develop["Exposure2012"]
                if wb_change is not None:
                    values.update(_apply_white_balance(photo, wb_change) or {})
                counts["from_anchor"] += 1
            elif not fill_unanchored:
                skipped[photo.image] = "no_edited_anchor_in_moment"
                continue
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
            else:
                skipped[photo.image] = "nothing_to_write"
    reasons: dict[str, int] = {}
    for reason in skipped.values():
        reasons[reason] = reasons.get(reason, 0) + 1
    summary = {"photos": sum(len(m) for m in moments), "moments": len(moments), "anchors": len(anchors),
               "anchors_edited": len(edited_anchors), **counts, "skipped": reasons}
    return {"edits": edits, "skipped": skipped, "summary": summary}
