import numpy as np

from app.brain_v2.encoder_comparison.contracts import (
    ComparisonDataset,
    FeatureMatrix,
)
from app.brain_v2.encoder_comparison.io import (
    load_dataset_npz,
    load_feature_npz,
    save_dataset_npz,
    save_feature_npz,
)


def test_dataset_npz_roundtrip(tmp_path) -> None:
    original = ComparisonDataset(
        sample_ids=("a", "b", "c", "d"),
        event_ids=("e1", "e1", "e2", "e2"),
        splits=("train", "train", "validation", "validation"),
        targets=np.ones((4, 3), dtype=np.float32),
    )

    path = tmp_path / "dataset.npz"
    save_dataset_npz(path, original)
    loaded = load_dataset_npz(path)

    assert loaded.sample_ids == original.sample_ids
    assert loaded.event_ids == original.event_ids
    assert np.array_equal(loaded.targets, original.targets)


def test_feature_npz_roundtrip(tmp_path) -> None:
    original = FeatureMatrix(
        candidate_id="clip",
        feature_version="clip-v1",
        sample_ids=("a", "b"),
        values=np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
    )

    path = tmp_path / "clip.npz"
    save_feature_npz(path, original)
    loaded = load_feature_npz(path)

    assert loaded.candidate_id == "clip"
    assert loaded.feature_version == "clip-v1"
    assert np.array_equal(loaded.values, original.values)
