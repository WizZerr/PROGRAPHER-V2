from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class TargetPrediction:
    sample_id: str
    candidate_id: str
    split: str
    exposure_pred: float
    temperature_pred: int
    tint_pred: int
    exposure_target: float
    temperature_target: int
    tint_target: int


@dataclass(frozen=True)
class CandidateMetrics:
    candidate_id: str
    samples: int
    exposure_mae: float
    temperature_mae: float
    tint_mae: float

    def to_dict(self) -> dict:
        return asdict(self)


def _mae(values: Iterable[tuple[float, float]]) -> float:
    pairs = list(values)
    if not pairs:
        raise ValueError("אין דוגמאות לחישוב MAE.")
    return sum(abs(pred - target) for pred, target in pairs) / len(pairs)


def evaluate_predictions(
    predictions: list[TargetPrediction],
    *,
    allowed_split: str,
) -> CandidateMetrics:
    if not predictions:
        raise ValueError("אין תחזיות להערכה.")

    candidate_ids = {item.candidate_id for item in predictions}
    if len(candidate_ids) != 1:
        raise ValueError("יש להעריך Candidate אחד בכל פעם.")

    wrong_split = [
        item.sample_id
        for item in predictions
        if item.split != allowed_split
    ]
    if wrong_split:
        raise ValueError(
            "ההשוואה כוללת דוגמאות מחוץ ל-split שנבחר."
        )

    candidate_id = next(iter(candidate_ids))

    return CandidateMetrics(
        candidate_id=candidate_id,
        samples=len(predictions),
        exposure_mae=_mae(
            (item.exposure_pred, item.exposure_target)
            for item in predictions
        ),
        temperature_mae=_mae(
            (float(item.temperature_pred), float(item.temperature_target))
            for item in predictions
        ),
        tint_mae=_mae(
            (float(item.tint_pred), float(item.tint_target))
            for item in predictions
        ),
    )
