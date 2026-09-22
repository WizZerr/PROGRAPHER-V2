from __future__ import annotations

from dataclasses import asdict, dataclass
import time

import numpy as np

from app.brain_v2.encoder_comparison.contracts import (
    ComparisonDataset,
    FeatureMatrix,
)
from app.brain_v2.encoder_comparison.metrics import regression_metrics
from app.brain_v2.encoder_comparison.predictor import (
    ExtraTreesConfig,
    FixedExtraTreesPredictor,
    MedianBaselinePredictor,
)


@dataclass(frozen=True)
class ComparisonConfig:
    predictor: ExtraTreesConfig = ExtraTreesConfig()

    def to_dict(self) -> dict:
        return {
            "predictor_id": FixedExtraTreesPredictor.predictor_id,
            "predictor": asdict(self.predictor),
        }


def _evaluate(
    *,
    predictor,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_validation: np.ndarray,
    y_validation: np.ndarray,
) -> tuple[dict, float, float]:
    fit_start = time.perf_counter()
    predictor.fit(x_train, y_train)
    fit_seconds = time.perf_counter() - fit_start

    predict_start = time.perf_counter()
    predictions = predictor.predict(x_validation)
    predict_seconds = time.perf_counter() - predict_start

    return (
        regression_metrics(y_validation, predictions),
        float(fit_seconds),
        float(predict_seconds),
    )


def compare_candidates(
    *,
    dataset: ComparisonDataset,
    candidates: tuple[FeatureMatrix, ...],
    config: ComparisonConfig | None = None,
) -> dict:
    dataset.validate()
    config = config or ComparisonConfig()
    config.predictor.validate()

    if not candidates:
        raise ValueError("נדרש candidate אחד לפחות.")

    candidate_ids = [item.candidate_id for item in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_id כפול.")

    train_mask = dataset.split_mask("train")
    validation_mask = dataset.split_mask("validation")
    y_train = dataset.targets[train_mask, :]
    y_validation = dataset.targets[validation_mask, :]

    dummy_train = np.zeros((int(train_mask.sum()), 1), dtype=np.float32)
    dummy_validation = np.zeros(
        (int(validation_mask.sum()), 1),
        dtype=np.float32,
    )
    baseline_metrics, baseline_fit, baseline_predict = _evaluate(
        predictor=MedianBaselinePredictor(),
        x_train=dummy_train,
        y_train=y_train,
        x_validation=dummy_validation,
        y_validation=y_validation,
    )

    reports: list[dict] = []

    for candidate in candidates:
        x = candidate.aligned_to(dataset)
        x_train = x[train_mask, :]
        x_validation = x[validation_mask, :]

        metrics, fit_seconds, predict_seconds = _evaluate(
            predictor=FixedExtraTreesPredictor(config=config.predictor),
            x_train=x_train,
            y_train=y_train,
            x_validation=x_validation,
            y_validation=y_validation,
        )

        reports.append(
            {
                "candidate_id": candidate.candidate_id,
                "feature_version": candidate.feature_version,
                "feature_dimension": int(x.shape[1]),
                "metrics": metrics,
                "fit_seconds": fit_seconds,
                "validation_predict_seconds": predict_seconds,
            }
        )

    return {
        "schema": "prographer.phase11.encoder-comparison.v1",
        "train_sample_count": int(train_mask.sum()),
        "validation_sample_count": int(validation_mask.sum()),
        "targets": list(dataset.target_names),
        "config": config.to_dict(),
        "baseline": {
            "predictor_id": MedianBaselinePredictor.predictor_id,
            "metrics": baseline_metrics,
            "fit_seconds": baseline_fit,
            "validation_predict_seconds": baseline_predict,
        },
        "candidates": reports,
        "decision": (
            "No candidate is promoted or ranked by this report. "
            "Promotion requires the later quality gate."
        ),
    }
