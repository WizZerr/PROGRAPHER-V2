import numpy as np
import pytest

from app.brain_v2.encoder_comparison.contracts import (
    ComparisonDataset,
    FeatureMatrix,
)


def dataset() -> ComparisonDataset:
    return ComparisonDataset(
        sample_ids=("a", "b", "c", "d"),
        event_ids=("event-1", "event-1", "event-2", "event-2"),
        splits=("train", "train", "validation", "validation"),
        targets=np.asarray(
            [
                [0.0, 5000.0, 0.0],
                [0.2, 5100.0, 1.0],
                [-0.1, 4900.0, -1.0],
                [0.1, 5050.0, 0.5],
            ],
            dtype=np.float32,
        ),
    )


def test_dataset_rejects_event_leakage() -> None:
    bad = ComparisonDataset(
        sample_ids=("a", "b", "c", "d"),
        event_ids=("same", "train2", "same", "val2"),
        splits=("train", "train", "validation", "validation"),
        targets=dataset().targets,
    )

    with pytest.raises(ValueError, match="Event leakage"):
        bad.validate()


def test_feature_matrix_reorders_to_dataset_ids() -> None:
    ds = dataset()
    matrix = FeatureMatrix(
        candidate_id="candidate",
        feature_version="v1",
        sample_ids=("d", "c", "b", "a"),
        values=np.asarray([[4.0], [3.0], [2.0], [1.0]], dtype=np.float32),
    )

    aligned = matrix.aligned_to(ds)
    assert aligned[:, 0].tolist() == [1.0, 2.0, 3.0, 4.0]


def test_feature_matrix_rejects_missing_samples() -> None:
    ds = dataset()
    matrix = FeatureMatrix(
        candidate_id="candidate",
        feature_version="v1",
        sample_ids=("a", "b", "c", "x"),
        values=np.ones((4, 2), dtype=np.float32),
    )

    with pytest.raises(ValueError, match="בדיוק את אותם samples"):
        matrix.aligned_to(ds)
