"""Synthetic tests for the v1 event brain (moments, anchors, completion). No catalog, no images."""
from __future__ import annotations

import statistics

import numpy as np
import pytest

from app.event_edit import brain
from app.event_edit.brain import Photo


def _photo(image, seconds, kelvin=5000.0, tint=5.0, **develop):
    return Photo(image=image, seconds=seconds, as_shot_kelvin=kelvin, as_shot_tint=tint,
                 develop={"WhiteBalance": "As Shot", "Exposure2012": 0.0, **develop})


def test_moments_split_on_pause_and_light_change():
    photos = [_photo(1, 0), _photo(2, 10), _photo(3, 50), _photo(4, 55, kelvin=3000.0), _photo(5, None)]
    moments = brain.make_moments(photos)
    assert [[p.image for p in m] for m in moments] == [[1, 2], [3], [4], [5]]


def test_anchor_count_and_choice():
    assert brain.default_anchor_count(100) == 20 and brain.default_anchor_count(3000) == 120
    assert brain.default_anchor_count(10000) == 150
    moments = [[_photo(1, 0)], [_photo(2, 100), _photo(3, 101), _photo(4, 102)], [_photo(5, 200), _photo(6, 201)]]
    assert [a.image for a in brain.choose_anchors(moments, 2)] == [3, 6]


def test_anchor_edit_is_copied_to_its_moment():
    anchor = _photo(2, 1, kelvin=4000.0, tint=3.0, Exposure2012=0.6, Highlights2012=-40, WhiteBalance="Custom",
                    Temperature=3800, Tint=6)
    anchor.edited_by_photographer = True
    other = _photo(3, 2, kelvin=4200.0, tint=1.0)
    moments = [[_photo(1, 0), anchor, other]]
    result = brain.complete_event(moments, [anchor])
    values = result["edits"][3]
    assert values["Exposure2012"] == 0.6 and values["Highlights2012"] == -40
    # the anchor moved 1e6/3800 - 1e6/4000 = +13.16 mired and +3 tint from its As Shot: same change on 4200 K / 1
    assert values["Temperature"] == round(1e6 / (1e6 / 4200 + (1e6 / 3800 - 1e6 / 4000)))
    assert values["Tint"] == 4
    assert 2 not in result["edits"] and result["summary"]["from_anchor"] == 1
    assert result["skipped"] == {1: "light_differs_from_anchor"}  # 5000 K vs the anchor's 4000 K: 50 mired


def test_anchor_left_as_shot_keeps_white_balance():
    anchor = _photo(1, 0, Exposure2012=0.3)
    anchor.edited_by_photographer = True
    result = brain.complete_event([[anchor, _photo(2, 1)]], [anchor])
    assert result["edits"][2] == {"Exposure2012": 0.3}


def test_moments_without_anchor_use_automatic_exposure_and_event_base():
    a1 = _photo(1, 0, Exposure2012=0.2, Clarity2012=-16)
    a2 = _photo(2, 100, Exposure2012=0.6, Clarity2012=-20)
    for a in (a1, a2):
        a.edited_by_photographer = True
    lone, faceless = _photo(3, 500), _photo(4, 900)
    moments = brain.make_moments([a1, a2, lone, faceless])
    auto = {3: 0.45}
    result = brain.complete_event(moments, [a1, a2], auto_exposure=lambda p: auto.get(p.image), fill_unanchored=True)
    assert result["edits"][3] == {"Clarity2012": -18, "Exposure2012": 0.45}
    assert result["edits"][4]["Exposure2012"] == pytest.approx(0.4)  # no automatic value: the anchors' median
    assert result["summary"]["automatic"] == 1 and result["summary"]["event_level"] == 1


def test_unedited_anchor_and_photographer_edits_are_respected():
    anchor = _photo(1, 0, Exposure2012=0.9)  # photographer has not edited it yet
    mine = _photo(2, 1, Exposure2012=-1.0)
    mine.edited_by_photographer = True
    result = brain.complete_event([[anchor, mine, _photo(3, 2)]], [anchor], fill_unanchored=True)
    assert 2 not in result["edits"] and result["summary"]["skipped_edited"] == 1
    assert result["edits"].get(3, {}).get("Exposure2012") is None  # nothing to copy, no automatic model given
    assert result["summary"]["anchors_edited"] == 0 and result["summary"]["no_exposure"] == 2


def test_exposure_target_recovers_a_darker_shooter():
    from app.event_edit import exposure_target as et

    curve = {"x": np.linspace(-14, 2, 200), "y": np.clip((np.linspace(-14, 2, 200) + 10) / 11, 0, 1) ** 0.8}
    rng = np.random.default_rng(1)
    shooter_a = []
    for _ in range(200):
        rgb = np.array([0.12, 0.09, 0.07]) * 2 ** rng.normal(0, 0.5)
        shooter_a.append({"face_rgb": rgb, "face_stops": float(np.log2(rgb @ et.LUMA)), "exposure": -0.35})
    style = et.learn_style(shooter_a, curve)
    darker = {i: {"face_rgb": f["face_rgb"] * 2 ** -0.65, "face_stops": f["face_stops"] - 0.65}
              for i, f in enumerate(shooter_a)}
    darker[999] = {}  # no face: gets the level
    exposures = et.automatic_exposures(darker, style, curve)
    assert exposures[999] == pytest.approx(0.30, abs=0.01)
    assert statistics.median(exposures.values()) == pytest.approx(0.30, abs=0.02)


def test_without_an_edited_anchor_photos_are_skipped_by_default():
    a = _photo(1, 0, Exposure2012=0.5)
    a.edited_by_photographer = True
    moments = brain.make_moments([a, _photo(2, 1), _photo(3, 500)])
    result = brain.complete_event(moments, [a])
    assert set(result["edits"]) == {2}
    assert result["skipped"] == {3: "no_edited_anchor_in_moment"}


def test_light_change_inside_a_moment_is_not_copied():
    a = _photo(1, 0, kelvin=5000.0, Exposure2012=0.5)
    a.edited_by_photographer = True
    drift = _photo(2, 1, kelvin=4300.0)  # 1e6/4300 - 1e6/5000 = 32.6 mired, beyond the 15 mired limit
    result = brain.complete_event([[a, drift]], [a])
    assert result["skipped"] == {2: "light_differs_from_anchor"}


def test_one_edited_anchor_in_a_3000_photo_event_is_blocked():
    photos = [_photo(i, i * 30.0) for i in range(3000)]  # 30 s apart: every photo its own moment
    moments = brain.make_moments(photos)
    anchors = brain.choose_anchors(moments, brain.default_anchor_count(3000))
    anchors[0].edited_by_photographer = True
    anchors[0].develop["Exposure2012"] = 0.8
    report = brain.assess_anchors(moments, anchors)
    assert not report["ok"] and report["blocking"][0]["reason"] == "too_few_edited_anchors"
    assert report["required_edited"] == 20 and report["anchors_edited"] == 1
    # even without the gate, nothing outside the anchor's own moment would be written
    result = brain.complete_event(moments, anchors)
    assert result["edits"] == {}
    assert result["summary"]["skipped"] == {"no_edited_anchor_in_moment": 2999}


def test_light_coverage_reports_bins_without_an_example():
    warm = [_photo(i, i, kelvin=3000.0) for i in range(5)]
    day = [_photo(100 + i, 1000 + i, kelvin=5500.0) for i in range(5)]
    moments = brain.make_moments(warm + day)
    anchors = brain.choose_anchors(moments, 2)
    next(a for a in anchors if a.as_shot_kelvin == 5500.0).edited_by_photographer = True
    report = brain.assess_anchors(moments, anchors)
    assert report["light_bins_without_example"] == ["0-3200K"] and report["covered_share"] == 0.5
