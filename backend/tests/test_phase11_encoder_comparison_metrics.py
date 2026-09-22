import numpy as np

from app.brain_v2.encoder_comparison.metrics import regression_metrics


def test_metrics_include_mae_median_p90_p95_per_target() -> None:
    truth = np.zeros((4, 3), dtype=np.float32)
    prediction = np.asarray(
        [
            [1.0, 100.0, 1.0],
            [2.0, 200.0, 2.0],
            [3.0, 300.0, 3.0],
            [4.0, 400.0, 4.0],
        ],
        dtype=np.float32,
    )

    result = regression_metrics(truth, prediction)

    exposure = result["targets"]["exposure_ev"]
    assert exposure["mae"] == 2.5
    assert exposure["median_ae"] == 2.5
    assert exposure["p90_ae"] > exposure["median_ae"]
    assert exposure["p95_ae"] >= exposure["p90_ae"]
