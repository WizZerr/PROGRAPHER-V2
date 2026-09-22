from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.brain_v2.encoder_comparison.contracts import (
    ComparisonDataset,
    FeatureMatrix,
)


def save_dataset_npz(path: str | Path, dataset: ComparisonDataset) -> None:
    dataset.validate()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        destination,
        sample_ids=np.asarray(dataset.sample_ids, dtype=str),
        event_ids=np.asarray(dataset.event_ids, dtype=str),
        splits=np.asarray(dataset.splits, dtype=str),
        targets=np.asarray(dataset.targets, dtype=np.float32),
        target_names=np.asarray(dataset.target_names, dtype=str),
    )


def load_dataset_npz(path: str | Path) -> ComparisonDataset:
    with np.load(Path(path), allow_pickle=False) as data:
        dataset = ComparisonDataset(
            sample_ids=tuple(str(x) for x in data["sample_ids"].tolist()),
            event_ids=tuple(str(x) for x in data["event_ids"].tolist()),
            splits=tuple(str(x) for x in data["splits"].tolist()),
            targets=np.asarray(data["targets"], dtype=np.float32),
            target_names=tuple(str(x) for x in data["target_names"].tolist()),
        )

    dataset.validate()
    return dataset


def save_feature_npz(path: str | Path, matrix: FeatureMatrix) -> None:
    matrix.validate()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        destination,
        candidate_id=np.asarray(matrix.candidate_id),
        feature_version=np.asarray(matrix.feature_version),
        sample_ids=np.asarray(matrix.sample_ids, dtype=str),
        values=np.asarray(matrix.values, dtype=np.float32),
    )


def load_feature_npz(path: str | Path) -> FeatureMatrix:
    with np.load(Path(path), allow_pickle=False) as data:
        matrix = FeatureMatrix(
            candidate_id=str(data["candidate_id"].item()),
            feature_version=str(data["feature_version"].item()),
            sample_ids=tuple(str(x) for x in data["sample_ids"].tolist()),
            values=np.asarray(data["values"], dtype=np.float32),
        )

    matrix.validate()
    return matrix


def write_json(path: str | Path, payload: dict) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
