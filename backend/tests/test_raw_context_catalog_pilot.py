"""RAW-CAT-01F.03A synthetic tests. No photographer media or names."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from app.photographer import raw_context_catalog_pilot as pilot


def test_selection_refuses_duplicate_keys(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    nested = raw / "nested"
    nested.mkdir()
    (raw / "PHOTO.CR3").write_bytes(b"x")
    (nested / "photo.cr3").write_bytes(b"y")
    files = pilot._index_originals(raw)
    rows = [{
        "file_stem": "PHOTO", "extension": "cr3",
        "event_group_id": "G0001", "parse_exclusion": None,
    }]
    selected, counts = pilot._candidate_selection(files, rows, 12)
    assert not selected
    assert counts["ambiguous_name_key"] == 1


def test_round_robin_uses_provisional_groups_only(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    rows = []
    for name, group in (("A", "G1"), ("B", "G1"), ("C", "G2")):
        (raw / (name + ".CR3")).write_bytes(b"sample")
        rows.append({
            "file_stem": name, "extension": "cr3",
            "event_group_id": group, "parse_exclusion": None,
        })
    selected, _ = pilot._candidate_selection(pilot._index_originals(raw), rows, 3)
    assert [row["event_group_id"] for _, row in selected] == ["G1", "G2", "G1"]


def test_source_and_develop_target_separated(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "PHOTO.CR3").write_bytes(b"not-a-real-raw")
    records = [{
        "file_stem": "PHOTO", "extension": "cr3", "catalog_image_id": 2,
        "event_group_id": "G1", "parse_exclusion": None,
        "virtual_copy_candidate": False,
        "develop": {"Exposure2012": 4.0},
        "complex": {"Look": {"present": True}},
        "unsupported_fields": ["Unsup"],
        "opaque_edit_review_required": True,
    }]
    monkeypatch.setattr(pilot, "inspect_catalog",
        lambda path, include_private=False: ({}, {"records": records}))
    meta = SimpleNamespace(
        preprocessing_version="fake-preprocess", raw_engine="fake",
        raw_engine_version="1.0", iso_speed=1600, shutter_seconds=0.01,
        aperture=2.8, focal_length_mm=35,
    )
    frame = SimpleNamespace(
        rgb_linear=np.full((8, 8, 3), 0.2, dtype=np.float32),
        source_sha256="abc", metadata=meta,
    )
    monkeypatch.setattr(pilot, "decode_raw", lambda path: frame)
    shared, private = pilot.build_pilot(raw, tmp_path / "unused.lrcat", 1)
    assert shared["decoded_and_catalog_linked_candidate"] == 1
    assert shared["training_ready_pairs"] == 0
    model_input = private["records"][0]["model_input_RESEARCH_ONLY"]
    target = private["records"][0]["target_UNAPPROVED_RESEARCH_ONLY"]
    assert "develop" not in str(model_input).lower()
    assert "Exposure2012" not in str(model_input)
    assert model_input["camera_metadata"]["iso_speed"] == 1600
    assert target["lightroom_develop"]["Exposure2012"] == 4.0
    assert private["records"][0]["photographer_review_PRIVATE"]["approved_for_training"] is False
    assert "PHOTO" not in str(shared)
    assert "Exposure2012" not in str(shared)
    assert "abc" not in str(shared)


def test_selection_spans_full_filename_range_in_each_provisional_group(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    rows = []
    for group in ("G1", "G2"):
        for i in range(10):
            name = f"{group}_PHOTO_{i:03d}"
            (raw / f"{name}.CR3").write_bytes(b"synthetic")
            rows.append({
                "file_stem": name, "extension": "cr3",
                "event_group_id": group, "parse_exclusion": None,
                "virtual_copy_candidate": False,
            })
    selected, counters = pilot._candidate_selection(pilot._index_originals(raw), rows, 6)
    assert [(row["event_group_id"], path.stem.split("_")[-1]) for path, row in selected] == [
        ("G1", "000"), ("G2", "000"),
        ("G1", "004"), ("G2", "004"),
        ("G1", "009"), ("G2", "009"),
    ]
    assert counters["selection_lexically_spread"] == 6


def test_selection_handles_small_group_without_duplicate_photos(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    rows = []
    for name, group in (("A", "G1"), ("B", "G2"), ("C", "G2"),
                        ("D", "G2"), ("E", "G2")):
        (raw / f"{name}.CR3").write_bytes(b"synthetic")
        rows.append({
            "file_stem": name, "extension": "cr3",
            "event_group_id": group, "parse_exclusion": None,
            "virtual_copy_candidate": False,
        })
    selected, _ = pilot._candidate_selection(pilot._index_originals(raw), rows, 5)
    assert len(selected) == 5
    assert len({path.name for path, _ in selected}) == 5
