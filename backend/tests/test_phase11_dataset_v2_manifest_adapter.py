import json

import numpy as np
import pytest

from app.brain_v2.encoder_comparison.manifest_adapter import (
    load_dataset_v2_manifest,
)


def _sample(
    sample_id,
    event_group,
    split,
    *,
    exposure=0.0,
    temperature=5000.0,
    tint=0.0,
):
    return {
        "sample_id": sample_id,
        "source_path": rf"C:\RAW\{sample_id}.CR3",
        "camera": {"make": "Canon", "model": "EOS R6"},
        "exif": {"iso": 100},
        "raw_info": {},
        "target_recipe": {
            "exposure": exposure,
            "temperature": temperature,
            "tint": tint,
        },
        "event_group": event_group,
        "capture_time": "2026-01-01T12:00:00",
        "split": split,
    }


def _valid_records():
    return [
        _sample("a", "event-train", "train"),
        _sample("b", "event-train", "train", exposure=0.2),
        _sample("c", "event-val", "validation", tint=-1.0),
        _sample("d", "event-val", "validation", temperature=5200.0),
    ]


def test_adapter_preserves_real_zero_targets(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_valid_records()), encoding="utf-8")

    selection = load_dataset_v2_manifest(path)

    assert selection.dataset.targets[0, 0] == 0.0
    assert selection.dataset.targets[0, 2] == 0.0


def test_adapter_excludes_test_without_touching_it(tmp_path) -> None:
    records = _valid_records()
    records.append(_sample("test-x", "event-test", "test"))

    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(records), encoding="utf-8")

    selection = load_dataset_v2_manifest(path)

    assert selection.manifest_total == 5
    assert selection.selected_total == 4
    assert selection.excluded_test == 1
    assert "test-x" not in selection.dataset.sample_ids


def test_adapter_rejects_missing_target_instead_of_using_zero(tmp_path) -> None:
    records = _valid_records()
    del records[0]["target_recipe"]["temperature"]

    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(records), encoding="utf-8")

    with pytest.raises(ValueError, match="temperature"):
        load_dataset_v2_manifest(path)


def test_adapter_rejects_event_leakage(tmp_path) -> None:
    records = _valid_records()
    records[2]["event_group"] = "event-train"

    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(records), encoding="utf-8")

    with pytest.raises(ValueError, match="Event leakage"):
        load_dataset_v2_manifest(path)


def test_adapter_supports_json_object_with_samples(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"version": "v2", "samples": _valid_records()}),
        encoding="utf-8",
    )

    selection = load_dataset_v2_manifest(path)
    assert selection.selected_total == 4


def test_adapter_supports_jsonl(tmp_path) -> None:
    path = tmp_path / "manifest.jsonl"
    path.write_text(
        "\n".join(json.dumps(item) for item in _valid_records()),
        encoding="utf-8",
    )

    selection = load_dataset_v2_manifest(path)
    assert selection.dataset.targets.shape == (4, 3)


def test_duplicate_sample_ids_are_rejected(tmp_path) -> None:
    records = _valid_records()
    records[3]["sample_id"] = "a"

    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(records), encoding="utf-8")

    with pytest.raises(ValueError, match="כפול"):
        load_dataset_v2_manifest(path)
