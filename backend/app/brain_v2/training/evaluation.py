from __future__ import annotations

import hashlib
import json
import math
import statistics
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.brain_v2.training.dataset_manifest import DatasetImportManifest
from app.brain_v2.training.event_split import EventSafeSplitManifest


TARGET_FIELDS = (
    "exposure_stops",
    "temperature_k",
    "tint",
)
METRIC_VERSION = "phase12-three-target-metrics-v1"


class CandidatePrediction(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_id: str
    exposure_stops: float
    temperature_k: float
    tint: float

    @field_validator("exposure_stops", "temperature_k", "tint")
    @classmethod
    def require_finite(cls, value: float) -> float:
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("prediction values must be finite")
        return value


class TargetMetricSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    n: int
    mae: float
    median_absolute_error: float
    p90_absolute_error: float
    p95_absolute_error: float


class CandidateEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_name: str
    dataset_id: str
    split_id: str
    metric_version: str
    validation_sample_count: int
    metrics: dict[str, TargetMetricSet]
    evaluation_id: str


class BaselineComparison(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_name: str
    baseline_name: str
    per_target: dict[str, dict[str, float | None]]


def _percentile_linear(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be between 0 and 1")

    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]

    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _metric_set(errors: list[float]) -> TargetMetricSet:
    if not errors:
        raise ValueError("metric calculation requires at least one error")

    return TargetMetricSet(
        n=len(errors),
        mae=sum(errors) / len(errors),
        median_absolute_error=statistics.median(errors),
        p90_absolute_error=_percentile_linear(errors, 0.90),
        p95_absolute_error=_percentile_linear(errors, 0.95),
    )


def _validation_truth(
    *,
    manifest: DatasetImportManifest,
    split: EventSafeSplitManifest,
) -> dict[str, dict[str, float]]:
    if split.dataset_id != manifest.dataset_id:
        raise ValueError(
            "split.dataset_id does not match manifest.dataset_id"
        )

    validation_ids = {
        item.sample_id
        for item in split.sample_assignments
        if item.split == "validation"
    }

    truth: dict[str, dict[str, float]] = {}
    for sample in manifest.samples:
        if sample.sample_id not in validation_ids:
            continue
        if not sample.ready_for_three_target_training:
            raise ValueError(
                "Validation split contains a sample that is not training-ready: "
                f"{sample.sample_id}"
            )
        if sample.targets is None:
            raise ValueError(
                f"Validation sample has no targets: {sample.sample_id}"
            )

        values: dict[str, float] = {}
        for field in TARGET_FIELDS:
            value = sample.targets.get(field)
            if value is None:
                raise ValueError(
                    f"Validation sample {sample.sample_id} is missing {field}"
                )
            values[field] = float(value)
        truth[sample.sample_id] = values

    if validation_ids != set(truth):
        missing = sorted(validation_ids - set(truth))
        raise ValueError(
            "Validation split references sample IDs absent from the manifest: "
            + ", ".join(missing)
        )

    if not truth:
        raise ValueError("Validation split contains no evaluable samples")

    return truth


def evaluate_candidate_predictions(
    *,
    manifest: DatasetImportManifest,
    split: EventSafeSplitManifest,
    candidate_name: str,
    predictions: list[CandidatePrediction],
) -> CandidateEvaluation:
    candidate_name = candidate_name.strip()
    if not candidate_name:
        raise ValueError("candidate_name must be non-empty")

    truth = _validation_truth(manifest=manifest, split=split)
    expected_ids = set(truth)

    by_id: dict[str, CandidatePrediction] = {}
    for prediction in predictions:
        if prediction.sample_id in by_id:
            raise ValueError(
                f"Duplicate prediction for sample_id={prediction.sample_id}"
            )
        by_id[prediction.sample_id] = prediction

    actual_ids = set(by_id)
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing predictions: {missing}")
        if extra:
            details.append(f"unexpected predictions: {extra}")
        raise ValueError(
            "Candidate predictions must match the validation cohort exactly; "
            + "; ".join(details)
        )

    errors: dict[str, list[float]] = {
        field: []
        for field in TARGET_FIELDS
    }

    for sample_id in sorted(expected_ids):
        prediction = by_id[sample_id]
        target = truth[sample_id]
        for field in TARGET_FIELDS:
            predicted = float(getattr(prediction, field))
            errors[field].append(
                abs(predicted - target[field])
            )

    metrics = {
        field: _metric_set(errors[field])
        for field in TARGET_FIELDS
    }

    identity_payload: dict[str, Any] = {
        "candidate_name": candidate_name,
        "dataset_id": manifest.dataset_id,
        "split_id": split.split_id,
        "metric_version": METRIC_VERSION,
        "predictions": [
            by_id[sample_id].model_dump(mode="json")
            for sample_id in sorted(by_id)
        ],
    }
    evaluation_id = hashlib.sha256(
        json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return CandidateEvaluation(
        candidate_name=candidate_name,
        dataset_id=manifest.dataset_id,
        split_id=split.split_id,
        metric_version=METRIC_VERSION,
        validation_sample_count=len(expected_ids),
        metrics=metrics,
        evaluation_id=evaluation_id,
    )


def compare_candidate_to_baseline(
    *,
    candidate: CandidateEvaluation,
    baseline: CandidateEvaluation,
) -> BaselineComparison:
    if candidate.dataset_id != baseline.dataset_id:
        raise ValueError("candidate and baseline use different dataset_id values")
    if candidate.split_id != baseline.split_id:
        raise ValueError("candidate and baseline use different split_id values")
    if candidate.metric_version != baseline.metric_version:
        raise ValueError(
            "candidate and baseline use different metric versions"
        )
    if candidate.validation_sample_count != baseline.validation_sample_count:
        raise ValueError(
            "candidate and baseline evaluated different sample counts"
        )

    per_target: dict[str, dict[str, float | None]] = {}
    for field in TARGET_FIELDS:
        candidate_mae = candidate.metrics[field].mae
        baseline_mae = baseline.metrics[field].mae
        absolute_improvement = baseline_mae - candidate_mae
        percent_improvement = (
            (absolute_improvement / baseline_mae) * 100.0
            if baseline_mae != 0.0
            else None
        )
        per_target[field] = {
            "baseline_mae": baseline_mae,
            "candidate_mae": candidate_mae,
            "mae_improvement_absolute": absolute_improvement,
            "mae_improvement_percent": percent_improvement,
        }

    return BaselineComparison(
        candidate_name=candidate.candidate_name,
        baseline_name=baseline.candidate_name,
        per_target=per_target,
    )
