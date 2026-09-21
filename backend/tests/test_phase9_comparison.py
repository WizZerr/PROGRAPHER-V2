import pytest

from app.evaluation.comparison import (
    TargetPrediction,
    evaluate_predictions,
)


def test_comparison_uses_one_candidate_and_one_split() -> None:
    predictions = [
        TargetPrediction(
            sample_id="a",
            candidate_id="baseline.train_median.v1",
            split="validation",
            exposure_pred=0.0,
            temperature_pred=5000,
            tint_pred=0,
            exposure_target=0.5,
            temperature_target=5200,
            tint_target=-5,
        ),
        TargetPrediction(
            sample_id="b",
            candidate_id="baseline.train_median.v1",
            split="validation",
            exposure_pred=0.0,
            temperature_pred=5000,
            tint_pred=0,
            exposure_target=-0.5,
            temperature_target=4800,
            tint_target=5,
        ),
    ]

    metrics = evaluate_predictions(
        predictions,
        allowed_split="validation",
    )

    assert metrics.exposure_mae == 0.5
    assert metrics.temperature_mae == 200.0
    assert metrics.tint_mae == 5.0


def test_comparison_rejects_split_leakage() -> None:
    prediction = TargetPrediction(
        sample_id="test-1",
        candidate_id="candidate",
        split="test",
        exposure_pred=0.0,
        temperature_pred=5000,
        tint_pred=0,
        exposure_target=0.0,
        temperature_target=5000,
        tint_target=0,
    )

    with pytest.raises(ValueError):
        evaluate_predictions(
            [prediction],
            allowed_split="validation",
        )
