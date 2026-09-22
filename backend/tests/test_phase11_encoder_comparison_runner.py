import numpy as np

from app.brain_v2.encoder_comparison.contracts import (
    ComparisonDataset,
    FeatureMatrix,
)
from app.brain_v2.encoder_comparison.predictor import ExtraTreesConfig
from app.brain_v2.encoder_comparison.runner import (
    ComparisonConfig,
    compare_candidates,
)


def test_candidates_use_same_dataset_and_predictor() -> None:
    sample_ids = tuple(f"s{i}" for i in range(12))
    event_ids = tuple(["train-event"] * 8 + ["validation-event"] * 4)
    splits = tuple(["train"] * 8 + ["validation"] * 4)

    base = np.arange(12, dtype=np.float32)
    targets = np.stack(
        (
            base * 0.1,
            5000.0 + base * 20.0,
            base - 5.0,
        ),
        axis=1,
    )

    dataset = ComparisonDataset(
        sample_ids=sample_ids,
        event_ids=event_ids,
        splits=splits,
        targets=targets,
    )

    measured = FeatureMatrix(
        candidate_id="measured",
        feature_version="v1",
        sample_ids=sample_ids,
        values=np.stack((base, base ** 2), axis=1),
    )
    clip = FeatureMatrix(
        candidate_id="clip",
        feature_version="v1",
        sample_ids=sample_ids,
        values=np.stack((base * 2.0, base + 1.0), axis=1),
    )

    report = compare_candidates(
        dataset=dataset,
        candidates=(measured, clip),
        config=ComparisonConfig(
            predictor=ExtraTreesConfig(
                n_estimators=16,
                min_samples_leaf=1,
                random_state=123,
                n_jobs=1,
            )
        ),
    )

    assert report["train_sample_count"] == 8
    assert report["validation_sample_count"] == 4
    assert len(report["candidates"]) == 2
    assert report["config"]["predictor_id"] == (
        "extratrees-independent-targets-v1"
    )
    assert report["decision"].startswith("No candidate")
