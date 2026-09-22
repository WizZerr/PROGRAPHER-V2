from __future__ import annotations

from dataclasses import dataclass

import numpy as np


TARGET_NAMES = (
    "exposure_ev",
    "temperature_k",
    "tint",
)

ALLOWED_SPLITS = {"train", "validation"}


@dataclass(frozen=True)
class ComparisonDataset:
    sample_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    splits: tuple[str, ...]
    targets: np.ndarray
    target_names: tuple[str, ...] = TARGET_NAMES

    def validate(self) -> None:
        n = len(self.sample_ids)

        if n < 4:
            raise ValueError("Comparison dataset קטן מדי.")
        if len(set(self.sample_ids)) != n:
            raise ValueError("sample_ids חייבים להיות ייחודיים.")
        if len(self.event_ids) != n or len(self.splits) != n:
            raise ValueError("sample/event/split lengths אינם תואמים.")
        if self.targets.shape != (n, len(self.target_names)):
            raise ValueError("targets shape אינו תואם לחוזה.")
        if tuple(self.target_names) != TARGET_NAMES:
            raise ValueError(
                "Phase 11 comparison targets חייבים Exposure/Temperature/Tint."
            )
        if not np.isfinite(self.targets).all():
            raise ValueError("targets מכילים NaN/Inf.")

        unknown = set(self.splits) - ALLOWED_SPLITS
        if unknown:
            raise ValueError(f"split לא נתמך: {sorted(unknown)}")
        if "train" not in self.splits or "validation" not in self.splits:
            raise ValueError("נדרשים גם train וגם validation.")

        train_events = {
            event
            for event, split in zip(self.event_ids, self.splits)
            if split == "train"
        }
        validation_events = {
            event
            for event, split in zip(self.event_ids, self.splits)
            if split == "validation"
        }

        overlap = train_events & validation_events
        if overlap:
            raise ValueError(
                "Event leakage בין train ל-validation: "
                + ", ".join(sorted(overlap)[:5])
            )

    def split_mask(self, split: str) -> np.ndarray:
        if split not in ALLOWED_SPLITS:
            raise ValueError(f"split לא נתמך: {split}")
        return np.asarray(
            [value == split for value in self.splits],
            dtype=bool,
        )


@dataclass(frozen=True)
class FeatureMatrix:
    candidate_id: str
    feature_version: str
    sample_ids: tuple[str, ...]
    values: np.ndarray

    def validate(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id חסר.")
        if not self.feature_version.strip():
            raise ValueError("feature_version חסרה.")
        if self.values.ndim != 2:
            raise ValueError("Feature matrix חייב להיות 2D.")
        if self.values.shape[0] != len(self.sample_ids):
            raise ValueError("Feature rows אינם תואמים ל-sample_ids.")
        if self.values.shape[1] < 1:
            raise ValueError("Feature matrix ריק.")
        if len(set(self.sample_ids)) != len(self.sample_ids):
            raise ValueError("Feature sample_ids אינם ייחודיים.")
        if not np.isfinite(self.values).all():
            raise ValueError("Feature matrix מכיל NaN/Inf.")

    def aligned_to(self, dataset: ComparisonDataset) -> np.ndarray:
        self.validate()
        dataset.validate()

        if self.sample_ids == dataset.sample_ids:
            return self.values

        index = {
            sample_id: row
            for row, sample_id in enumerate(self.sample_ids)
        }

        missing = [
            sample_id
            for sample_id in dataset.sample_ids
            if sample_id not in index
        ]
        extras = set(self.sample_ids) - set(dataset.sample_ids)

        if missing or extras:
            raise ValueError(
                "Candidate אינו מכיל בדיוק את אותם samples. "
                f"missing={len(missing)}, extras={len(extras)}"
            )

        order = [index[sample_id] for sample_id in dataset.sample_ids]
        return self.values[np.asarray(order, dtype=np.int64), :]
