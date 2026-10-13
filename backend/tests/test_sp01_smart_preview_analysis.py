"""SP-01 synthetic-only tests: no real photos, Lightroom, CUDA or network."""
from __future__ import annotations

import json

import numpy as np
from PIL import Image
import pytest

from app.photographer import smart_preview_analysis as sp


def _jpeg(tmp_path, name="NEUTRAL.jpg"):
    rng = np.random.default_rng(101)
    rgb = rng.integers(0, 255, size=(128, 128, 3), dtype=np.uint8)
    path = tmp_path / name
    Image.fromarray(rgb, mode="RGB").save(path, format="JPEG", quality=93)
    assert path.stat().st_size >= 1024
    return path


class FakeSceneAI:
    def predict(self, image):
        assert image.mode == "RGB"
        return {
            "raw_top_label": "DANCING",
            "suggested_label": "DANCING",
            "relative_top_score": .71,
            "relative_margin": .55,
            "abstained": False,
        }


def test_normalized_srgb_not_raw_linear():
    rgb = Image.fromarray(np.full((24, 24, 3), 128, dtype=np.uint8))
    result = sp.srgb_visual_metrics(rgb)
    assert result["linearized_srgb_luminance_p50"] == pytest.approx(.21586, abs=.0005)
    assert result["display_srgb_mean_red"] == pytest.approx(128 / 255, abs=.00001)
    assert "raw_engine" not in result
    assert "fraction_luminance_below_0_03" not in result


def test_dark_and_bright_display_measurements():
    dark = sp.srgb_visual_metrics(Image.new("RGB", (8, 8), (0, 0, 0)))
    light = sp.srgb_visual_metrics(Image.new("RGB", (8, 8), (255, 255, 255)))
    assert dark["linearized_srgb_fraction_below_0_03"] == 1
    assert light["linearized_srgb_fraction_below_0_03"] == 0
    assert light["display_srgb_fraction_near_white"] == 1


def test_neutral_analysis_never_includes_edit_target(tmp_path):
    src = _jpeg(tmp_path)
    original = src.read_bytes()
    result = sp.analyze_neutral_jpeg(src)
    assert result["scene"]["status"] == "AI_NOT_RUN"
    assert result["scene"]["suggested_label"] == "UNKNOWN"
    assert result["source_kind"] == "USER_PREPARED_SMART_PREVIEW_NEUTRAL_JPEG_UNVERIFIED"
    assert result["photographer_develop_target_in_model_input"] is False
    assert result["independent_neutrality_leakage_gate_passed"] is False
    assert result["training_ready"] is False
    assert "lightroom_develop" not in result
    assert src.read_bytes() == original


def test_existing_scene_predictor_only_receives_neutral_image(tmp_path):
    result = sp.analyze_neutral_jpeg(_jpeg(tmp_path), predictor=FakeSceneAI())
    assert result["scene"]["suggested_label"] == "DANCING"
    assert result["scene"]["status"] == "ZERO_SHOT_UNCALIBRATED_HUMAN_REVIEW_REQUIRED"
    assert result["training_ready"] is False


@pytest.mark.parametrize("bad_guess", [
    {"suggested_label": "FAKE", "abstained": False},
    {"suggested_label": "DANCING", "abstained": True},
])
def test_scene_predictions_fail_closed(tmp_path, bad_guess):
    class InvalidPredictor:
        def predict(self, _):
            return bad_guess
    with pytest.raises(ValueError):
        sp.analyze_neutral_jpeg(_jpeg(tmp_path), predictor=InvalidPredictor())


def test_rejects_bad_extensions_and_fake_jpeg(tmp_path):
    png = tmp_path / "fake.png"
    noise = np.random.default_rng(5).integers(0, 255, size=(128, 128, 3), dtype=np.uint8)
    Image.fromarray(noise, mode="RGB").save(png)
    assert png.stat().st_size > 1024
    with pytest.raises(ValueError, match="JPEG"):
        sp.read_neutral_jpeg(png)
    wrong = tmp_path / "renamed.jpg"
    wrong.write_bytes(png.read_bytes())
    with pytest.raises(ValueError, match="not a JPEG"):
        sp.read_neutral_jpeg(wrong)


def test_source_change_between_reads_is_rejected(tmp_path, monkeypatch):
    source = _jpeg(tmp_path)
    real = sp._digest
    n = 0
    def inconsistent_digest(path):
        nonlocal n
        n += 1
        return "f" * 64 if n == 2 else real(path)
    monkeypatch.setattr(sp, "_digest", inconsistent_digest)
    with pytest.raises(ValueError, match="changed"):
        sp.read_neutral_jpeg(source)


def _research_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(sp.Path, "home", lambda: tmp_path)
    root = tmp_path / "Documents" / sp.RESEARCH_ROOT_NAME
    source_dir = root / "SP_01_OFFLINE_NEUTRAL_EXPORT"
    source_dir.mkdir(parents=True)
    src = _jpeg(source_dir)
    return root, src


def test_private_output_isolated_and_aggregate_has_no_identity(tmp_path, monkeypatch):
    root, src = _research_paths(tmp_path, monkeypatch)
    dest = root / "SP_01_OUTPUT"
    result = sp.run_research(src, dest, predictor=FakeSceneAI())
    assert result["analyzed"] == 1
    assert result["training_ready"] == 0
    private = json.loads((dest / "SP01_ANALYSIS_PRIVATE.json").read_text(encoding="utf-8"))
    assert private["scene"]["raw_top_label"] == "DANCING"
    aggregate_text = (dest / "SP01_AGGREGATE.json").read_text(encoding="utf-8")
    assert str(src) not in aggregate_text
    assert src.name not in aggregate_text
    assert private["source_sha256_PRIVATE"] not in aggregate_text
    assert "DANCING" not in aggregate_text


def test_no_overwrite_prior_research_result(tmp_path, monkeypatch):
    root, src = _research_paths(tmp_path, monkeypatch)
    dest = root / "SP_01_OUTPUT"
    sp.run_research(src, dest)
    original = (dest / "SP01_ANALYSIS_PRIVATE.json").read_bytes()
    with pytest.raises(ValueError, match="new or empty"):
        sp.run_research(src, dest)
    assert (dest / "SP01_ANALYSIS_PRIVATE.json").read_bytes() == original


def test_rejects_outside_research_root_and_input_parent(tmp_path, monkeypatch):
    root, src = _research_paths(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="private research"):
        sp._private_paths(src, tmp_path / "OUTSIDE")
    with pytest.raises(ValueError, match="private research"):
        sp._private_paths(src, src.parent / "CHILD")


def test_rejects_symlink_input(tmp_path, monkeypatch):
    root, src = _research_paths(tmp_path, monkeypatch)
    link = src.parent / "copy.jpg"
    try:
        link.symlink_to(src)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError, match="symlink"):
        sp._private_paths(link, root / "OUT")


def test_research_sdk_adapter_is_read_only_and_test_catalog_limited():
    """Static guard; Lightroom behavior still requires a real Windows smoke."""
    lua = (
        sp.Path(__file__).resolve().parents[2]
        / "integrations/lightroom_classic/sp01"
        / "ProGrapherSmartPreviewResearch.lrdevplugin/ExportNeutralCopy.lua"
    ).read_text(encoding="utf-8")
    assert "SP_01_OFFLINE_PROOF.lrcat" in lua
    assert "neutralCopy:getRawMetadata('isVirtualCopy')" in lua
    assert "neutralCopy:checkPhotoAvailability()" in lua
    assert "original:getDevelopSettings()" in lua
    assert "training_ready=false" in lua
    for forbidden in (
        "withWriteAccessDo(", "applyDevelopSettings(", "resetAllDevelopAdjustments(",
        "createVirtualCopies(", "deleteSmartPreview(", "setRawMetadata(",
    ):
        assert forbidden not in lua, f"Research exporter must not mutate catalog: {forbidden}"
