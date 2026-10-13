"""SP-01.03 synthetic only: all-rank evaluation; never feeds human labels into CLIP."""
from __future__ import annotations

import json

import numpy as np
from PIL import Image
import pytest

from app.photographer import smart_preview_ranked_scene as ranked
from app.photographer import smart_preview_analysis as sp
from app.photographer.raw_auto_scene_review import PROMPT_KEYS

# CEREMONY top-1, PORTRAIT second, same .0716 margin as the observed
# offline Smart Preview research run. SYNTHETIC values, not model evidence.
SCORES = {
    "GETTING_READY": 0.15,
    "CEREMONY": 0.256,
    "DANCING": 0.13,
    "PORTRAIT": 0.1844,
    "GROUP_PORTRAIT": 0.10,
    "RECEPTION": 0.09,
    "DETAILS": 0.06,
    "OTHER": 0.0296,
}


def _scores():
    return [SCORES[key] for key in PROMPT_KEYS]


def _jpeg(tmp_path):
    rng = np.random.default_rng(54)
    pixels = rng.integers(0, 255, (144, 144, 3), dtype=np.uint8)
    src = tmp_path / "neutral.jpg"
    Image.fromarray(pixels, mode="RGB").save(src, quality=91)
    assert src.stat().st_size > 1024
    return src


class FakeRankedPredictor:
    def predict(self, image):
        assert image.mode == "RGB"
        assert image.width == 144
        return ranked.ranked_scene_report(_scores())


def test_all_eight_scores_preserved_and_abstention_unchanged():
    result = ranked.ranked_scene_report(_scores())
    assert result["raw_top_label"] == "CEREMONY"
    assert result["suggested_label"] == "UNKNOWN"
    assert result["abstained"] is True
    assert result["relative_margin"] == pytest.approx(0.0716)
    assert [entry["label"] for entry in result["top_3"]] == [
        "CEREMONY", "PORTRAIT", "GETTING_READY"
    ]
    assert len(result["ranking"]) == len(PROMPT_KEYS) == 8
    assert [entry["rank"] for entry in result["ranking"]] == list(range(1, 9))
    assert sum(entry["relative_score"] for entry in result["ranking"]) == pytest.approx(1)
    assert result["scores_are_calibrated_probabilities"] is False
    assert len(result["prompt_sha256"]) == 64


def test_ground_truth_added_after_inference_and_never_changes_prediction():
    prediction = ranked.ranked_scene_report(_scores())
    serialized = json.dumps(prediction, sort_keys=True)
    assessment = ranked.after_inference_human_review(prediction, "PORTRAIT")
    assert assessment["human_confirmed_scene"] == "PORTRAIT"
    assert assessment["human_label_is_model_input"] is False
    assert assessment["ground_truth_rank"] == 2
    assert assessment["top_1_matches_ground_truth"] is False
    assert assessment["safe_abstention_on_wrong_top_1"] is True
    assert json.dumps(prediction, sort_keys=True) == serialized


def test_invalid_manual_label_fails_closed():
    with pytest.raises(ValueError, match="human label"):
        ranked.after_inference_human_review(ranked.ranked_scene_report(_scores()), "UNKNOWN")


@pytest.mark.parametrize("scores", [
    [0.5, 0.5],
    [float("nan")] * 8,
    [float("inf")] * 8,
    [-0.05] + [0.15] * 7,
])
def test_invalid_model_distribution_is_rejected(scores):
    with pytest.raises(ValueError):
        ranked.ranked_scene_report(scores)


def test_human_review_requires_full_ranking():
    with pytest.raises(ValueError, match="complete"):
        ranked.after_inference_human_review({"raw_top_label": "CEREMONY"}, "PORTRAIT")


def test_real_pipeline_path_uses_neutral_only_and_keeps_human_review_private(tmp_path, monkeypatch):
    monkeypatch.setattr(sp.Path, "home", lambda: tmp_path)
    root = tmp_path / "Documents" / sp.RESEARCH_ROOT_NAME
    folder = root / "neutral"
    folder.mkdir(parents=True)
    jpeg = _jpeg(folder)
    jpeg_hash = sp._digest(jpeg)
    output = root / "report"

    result = sp.run_research(
        jpeg, output, predictor=FakeRankedPredictor(), human_scene="PORTRAIT"
    )
    assert result["training_ready"] == 0
    private = json.loads((output / "SP01_ANALYSIS_PRIVATE.json").read_text(encoding="utf-8"))
    assert len(private["scene"]["ranking"]) == 8
    assert private["human_review_PRIVATE"]["ground_truth_rank"] == 2
    assert private["human_review_PRIVATE"]["top_1_matches_ground_truth"] is False
    assert private["photographer_develop_target_in_model_input"] is False
    assert private["training_ready"] is False
    assert sp._digest(jpeg) == jpeg_hash

    aggregate = (output / "SP01_AGGREGATE.json").read_text(encoding="utf-8")
    assert str(jpeg) not in aggregate
    assert jpeg.name not in aggregate
    assert jpeg_hash not in aggregate
    assert "PORTRAIT" not in aggregate
    assert "CEREMONY" not in aggregate


def test_invalid_human_scene_does_not_write_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(sp.Path, "home", lambda: tmp_path)
    root = tmp_path / "Documents" / sp.RESEARCH_ROOT_NAME
    folder = root / "neutral"
    folder.mkdir(parents=True)
    jpeg = _jpeg(folder)
    output = root / "report"
    with pytest.raises(ValueError):
        sp.run_research(
            jpeg, output, predictor=FakeRankedPredictor(), human_scene="UNKNOWN"
        )
    assert not output.exists()
