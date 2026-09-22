from __future__ import annotations

import numpy as np

from app.brain_v2.encoder_comparison.contracts import TARGET_NAMES


def regression_metrics(
    truth: np.ndarray,
    prediction: np.ndarray,
) -> dict:
    if truth.shape != prediction.shape:
        raise ValueError("truth/prediction shapes אינם תואמים.")
    if truth.ndim != 2 or truth.shape[1] != len(TARGET_NAMES):
        raise ValueError("Metric input shape אינו תקין.")

    absolute = np.abs(prediction - truth)
    targets: dict[str, dict[str, float]] = {}

    for index, target_name in enumerate(TARGET_NAMES):
        values = absolute[:, index]
        targets[target_name] = {
            "mae": float(np.mean(values)),
            "median_ae": float(np.median(values)),
            "p90_ae": float(np.percentile(values, 90)),
            "p95_ae": float(np.percentile(values, 95)),
        }

    return {
        "sample_count": int(truth.shape[0]),
        "targets": targets,
    }
