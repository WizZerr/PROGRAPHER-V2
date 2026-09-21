from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any


TARGETS = ("exposure", "temperature", "tint")


@dataclass(frozen=True)
class MedianBaseline:
    exposure: float
    temperature: int
    tint: int
    fitted_samples: int
    source_split: str = "train"

    def predict(self) -> dict[str, float | int]:
        return {
            "exposure": self.exposure,
            "temperature": self.temperature,
            "tint": self.tint,
        }


def fit_train_median_baseline(
    manifest: dict[str, Any],
) -> MedianBaseline:
    values: dict[str, list[float]] = {
        "exposure": [],
        "temperature": [],
        "tint": [],
    }

    usable_count = 0

    for sample in manifest.get("samples", []):
        if sample.get("split") != "train":
            continue

        if not sample.get("usable_for_training", False):
            continue

        recipe = sample.get("target_recipe") or {}

        if any(recipe.get(name) is None for name in TARGETS):
            continue

        values["exposure"].append(float(recipe["exposure"]))
        values["temperature"].append(float(recipe["temperature"]))
        values["tint"].append(float(recipe["tint"]))
        usable_count += 1

    if usable_count == 0:
        raise ValueError(
            "אין דוגמאות Train מאומתות עם Exposure/Temperature/Tint."
        )

    return MedianBaseline(
        exposure=float(median(values["exposure"])),
        temperature=int(round(median(values["temperature"]))),
        tint=int(round(median(values["tint"]))),
        fitted_samples=usable_count,
    )
