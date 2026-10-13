"""SP-01.04 synthetic repeatability gate — NO Lightroom/photos/network."""
from __future__ import annotations

import json

import numpy as np
from PIL import Image
import pytest

from app.photographer import smart_preview_repeatability as rr
from app.photographer import smart_preview_analysis as sp


def _private_pair(tmp_path, monkeypatch, *, variants=(0, 0)):
    monkeypatch.setattr(sp.Path, "home", lambda: tmp_path)
    root = tmp_path / "Documents" / sp.RESEARCH_ROOT_NAME
    a_folder = root / "export_a"
    b_folder = root / "export_b"
    a_folder.mkdir(parents=True)
    b_folder.mkdir(parents=True)
    rng = np.random.default_rng(123)
    pixels = rng.integers(0, 255, (128, 128, 3), dtype=np.uint8)
    outputs = []
    for folder, value in zip((a_folder, b_folder), variants):
        data = pixels.copy()
        if value:
            data[0, 0, 0] = (int(data[0, 0, 0]) + value) % 256
        path = folder / "neutral.jpg"
        Image.fromarray(data).save(path, format="JPEG", quality=95)
        assert path.stat().st_size >= 1024
        outputs.append(path)
    return root, outputs[0], outputs[1]


def test_identical_pixels_are_repeatability_candidate(tmp_path, monkeypatch):
    root, a, b = _private_pair(tmp_path, monkeypatch)
    before_a, before_b = a.read_bytes(), b.read_bytes()
    result = rr.run_research(a, b, root / "repeat_check")
    assert result["pixel_equal"] is True
    assert result["candidate_repeatability_pass"] is True
    assert result["mean_absolute_rgb_difference_8bit"] == 0
    assert result["max_absolute_rgb_difference_8bit"] == 0
    assert result["byte_hashes_match"] is True
    assert result["neutrality_independent_of_master_develop_proven"] is False
    assert result["learning_eligibility"] is False
    assert a.read_bytes() == before_a and b.read_bytes() == before_b
    report = (root / "repeat_check" / "SP01_REPEATABILITY_AGGREGATE.json").read_text(
        encoding="utf-8"
    )
    assert str(a) not in report and str(b) not in report
    assert a.name not in report
    assert sp._digest(a) not in report
    assert json.loads(report)["pixel_equal"] is True


def test_one_changed_pixel_cannot_pass_strict_repeatability(tmp_path, monkeypatch):
    _, a, b = _private_pair(tmp_path, monkeypatch, variants=(0, 16))
    result = rr.compare_decoded_jpegs(a, b)
    assert result["pixel_equal"] is False
    assert result["mean_absolute_rgb_difference_8bit"] > 0
    assert result["candidate_repeatability_pass"] is False
    assert result["fraction_pixels_all_channels_exact_match"] < 1


def test_different_dimensions_fail(tmp_path, monkeypatch):
    root, a, b = _private_pair(tmp_path, monkeypatch)
    image = Image.open(b).convert("RGB")
    image.crop((0, 0, 100, 100)).save(b, quality=95)
    result = rr.compare_decoded_jpegs(a, b)
    assert result["dimensions_match"] is False
    assert result["candidate_repeatability_pass"] is False
    assert result["mean_absolute_rgb_difference_8bit"] is None


def test_same_source_file_rejected(tmp_path, monkeypatch):
    root, a, _ = _private_pair(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="same input|separate files"):
        rr.run_research(a, a, root / "out")
    assert not (root / "out").exists()


def test_no_overwrite_existing_results(tmp_path, monkeypatch):
    root, a, b = _private_pair(tmp_path, monkeypatch)
    dest = root / "out"
    rr.run_research(a, b, dest)
    previous = (dest / "SP01_REPEATABILITY_AGGREGATE.json").read_bytes()
    with pytest.raises(ValueError, match="not empty"):
        rr.run_research(a, b, dest)
    assert (dest / "SP01_REPEATABILITY_AGGREGATE.json").read_bytes() == previous


def test_output_must_be_in_research_root_and_outside_inputs(tmp_path, monkeypatch):
    root, a, b = _private_pair(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="outside"):
        rr.run_research(a, b, tmp_path / "outside")
    with pytest.raises(ValueError, match="under input"):
        rr.run_research(a, b, a.parent / "result")


def test_mismatched_png_extension_is_rejected(tmp_path, monkeypatch):
    root, a, b = _private_pair(tmp_path, monkeypatch)
    fake = root / "export_b" / "not_jpeg.png"
    Image.new("RGB", (128, 128), "white").save(fake)
    with pytest.raises(ValueError, match="JPEG"):
        rr.run_research(a, fake, root / "out")
    assert not (root / "out").exists()
