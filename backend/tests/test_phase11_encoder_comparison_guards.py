import numpy as np
import pytest

from app.brain_v2.encoder_comparison.contracts import (
    ComparisonDataset,
    FeatureMatrix,
)
from app.brain_v2.encoder_comparison.runner import compare_candidates


def _dataset() -> ComparisonDataset:
    return ComparisonDataset(
        sample_ids=("a", "b", "c", "d"),
        event_ids=("e1", "e1", "e2", "e2"),
        splits=("train", "train", "validation", "validation"),
        targets=np.ones((4, 3), dtype=np.float32),
    )


def test_duplicate_candidate_ids_are_rejected() -> None:
    matrix = FeatureMatrix(
        candidate_id="same",
        feature_version="v1",
        sample_ids=("a", "b", "c", "d"),
        values=np.ones((4, 2), dtype=np.float32),
    )

    with pytest.raises(ValueError, match="כפול"):
        compare_candidates(
            dataset=_dataset(),
            candidates=(matrix, matrix),
        )


def test_test_split_is_not_allowed_in_phase11_harness() -> None:
    dataset = ComparisonDataset(
        sample_ids=("a", "b", "c", "d"),
        event_ids=("e1", "e1", "e2", "e3"),
        splits=("train", "train", "validation", "test"),
        targets=np.ones((4, 3), dtype=np.float32),
    )

    with pytest.raises(ValueError, match="split"):
        dataset.validate()
