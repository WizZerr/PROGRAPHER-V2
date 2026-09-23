from __future__ import annotations

import hashlib
import json
import statistics
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.brain_v2.training.dataset_manifest import DatasetImportManifest
from app.brain_v2.training.evaluation import CandidatePrediction
from app.brain_v2.training.event_split import EventSafeSplitManifest


BaselineStrategy = Literal["median", "mean"]
TARGET_FIELDS = ("exposure_stops", "temperature_k", "tint")
BASELINE_VERSION = "phase12-simple-target-baseline-v1"


class BaselineModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    baseline_version: str = BASELINE_VERSION
    strategy: BaselineStrategy
    dataset_id: str
    split_id: str
    train_sample_count: int
    fitted_values: dict[str, float]


class BaselinePredictionBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline: BaselineModel
    validation_sample_count: int
    predictions: tuple[CandidatePrediction, ...]


def _cohort_ids(
    split: EventSafeSplitManifest,
    split_name: Literal["train", "validation"],
) -> set[str]:
    return {
        item.sample_id
        for item in split.sample_assignments
        if item.split == split_name
    }


def _ready_targets_by_id(
    manifest: DatasetImportManifest,
) -> dict[str, dict[str, float]]:
    values: dict[str, dict[str, float]] = {}
    for sample in manifest.samples:
        if not sample.ready_for_three_target_training:
            continue
        if sample.targets is None:
            raise ValueError(
                f"Training-ready sample has no targets: {sample.sample_id}"
            )

        row: dict[str, float] = {}
        for field in TARGET_FIELDS:
            value = sample.targets.get(field)
            if value is None:
                raise ValueError(
                    f"Training-ready sample {sample.sample_id} is missing {field}"
                )
            row[field] = float(value)
        values[sample.sample_id] = row
    return values


def fit_simple_baseline(
    *,
    manifest: DatasetImportManifest,
    split: EventSafeSplitManifest,
    strategy: BaselineStrategy = "median",
) -> BaselineModel:
    if split.dataset_id != manifest.dataset_id:
        raise ValueError(
            "split.dataset_id does not match manifest.dataset_id"
        )

    train_ids = _cohort_ids(split, "train")
    if not train_ids:
        raise ValueError("Train split contains no samples")

    targets_by_id = _ready_targets_by_id(manifest)
    missing = sorted(train_ids - set(targets_by_id))
    if missing:
        raise ValueError(
            "Train split references missing/non-ready samples: "
            + ", ".join(missing)
        )

    fitted: dict[str, float] = {}
    for field in TARGET_FIELDS:
        values = [
            targets_by_id[sample_id][field]
            for sample_id in sorted(train_ids)
        ]
        if strategy == "median":
            fitted[field] = float(statistics.median(values))
        elif strategy == "mean":
            fitted[field] = float(statistics.fmean(values))
        else:
            raise ValueError(f"Unsupported baseline strategy: {strategy}")

    identity_payload = {
        "baseline_version": BASELINE_VERSION,
        "strategy": strategy,
        "dataset_id": manifest.dataset_id,
        "split_id": split.split_id,
        "train_sample_ids": sorted(train_ids),
        "fitted_values": fitted,
    }
    baseline_id = hashlib.sha256(
        json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return BaselineModel(
        baseline_id=baseline_id,
        strategy=strategy,
        dataset_id=manifest.dataset_id,
        split_id=split.split_id,
        train_sample_count=len(train_ids),
        fitted_values=fitted,
    )


def generate_validation_predictions(
    *,
    manifest: DatasetImportManifest,
    split: EventSafeSplitManifest,
    baseline: BaselineModel,
) -> BaselinePredictionBundle:
    if baseline.dataset_id != manifest.dataset_id:
        raise ValueError(
            "baseline.dataset_id does not match manifest.dataset_id"
        )
    if baseline.split_id != split.split_id:
        raise ValueError(
            "baseline.split_id does not match split.split_id"
        )

    validation_ids = _cohort_ids(split, "validation")
    if not validation_ids:
        raise ValueError("Validation split contains no samples")

    targets_by_id = _ready_targets_by_id(manifest)
    missing = sorted(validation_ids - set(targets_by_id))
    if missing:
        raise ValueError(
            "Validation split references missing/non-ready samples: "
            + ", ".join(missing)
        )

    predictions = tuple(
        CandidatePrediction(
            sample_id=sample_id,
            exposure_stops=baseline.fitted_values["exposure_stops"],
            temperature_k=baseline.fitted_values["temperature_k"],
            tint=baseline.fitted_values["tint"],
        )
        for sample_id in sorted(validation_ids)
    )

    return BaselinePredictionBundle(
        baseline=baseline,
        validation_sample_count=len(predictions),
        predictions=predictions,
    )
