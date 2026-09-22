from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ExtraTreesConfig:
    n_estimators: int = 300
    min_samples_leaf: int = 2
    max_features: float = 1.0
    random_state: int = 20260922
    n_jobs: int = -1

    def validate(self) -> None:
        if self.n_estimators < 1:
            raise ValueError("n_estimators חייב להיות חיובי.")
        if self.min_samples_leaf < 1:
            raise ValueError("min_samples_leaf חייב להיות חיובי.")
        if not 0.0 < self.max_features <= 1.0:
            raise ValueError("max_features חייב להיות בטווח (0,1].")


class FixedExtraTreesPredictor:
    predictor_id = "extratrees-independent-targets-v1"

    def __init__(self, config: ExtraTreesConfig | None = None) -> None:
        self.config = config or ExtraTreesConfig()
        self.config.validate()
        self._models = []

    def fit(self, x: np.ndarray, y: np.ndarray) -> "FixedExtraTreesPredictor":
        from sklearn.ensemble import ExtraTreesRegressor

        if x.ndim != 2 or y.ndim != 2:
            raise ValueError("x/y חייבים להיות 2D.")
        if x.shape[0] != y.shape[0]:
            raise ValueError("x/y rows אינם תואמים.")

        self._models = []

        for target_index in range(y.shape[1]):
            model = ExtraTreesRegressor(
                n_estimators=self.config.n_estimators,
                min_samples_leaf=self.config.min_samples_leaf,
                max_features=self.config.max_features,
                random_state=self.config.random_state + target_index,
                n_jobs=self.config.n_jobs,
            )
            model.fit(x, y[:, target_index])
            self._models.append(model)

        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        if not self._models:
            raise RuntimeError("יש לקרוא fit() לפני predict().")

        predictions = [model.predict(x) for model in self._models]
        return np.stack(predictions, axis=1)


class MedianBaselinePredictor:
    predictor_id = "train-median-baseline-v1"

    def __init__(self) -> None:
        self._median: np.ndarray | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "MedianBaselinePredictor":
        del x
        self._median = np.median(y, axis=0)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self._median is None:
            raise RuntimeError("יש לקרוא fit() לפני predict().")

        return np.repeat(
            self._median.reshape(1, -1),
            repeats=x.shape[0],
            axis=0,
        )
