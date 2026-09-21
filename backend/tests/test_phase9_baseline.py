from app.evaluation.baseline import fit_train_median_baseline


def test_baseline_fits_train_only() -> None:
    manifest = {
        "samples": [
            {
                "split": "train",
                "usable_for_training": True,
                "target_recipe": {
                    "exposure": 0.0,
                    "temperature": 5000,
                    "tint": 0,
                },
            },
            {
                "split": "train",
                "usable_for_training": True,
                "target_recipe": {
                    "exposure": 1.0,
                    "temperature": 6000,
                    "tint": 10,
                },
            },
            {
                "split": "test",
                "usable_for_training": True,
                "target_recipe": {
                    "exposure": 99.0,
                    "temperature": 99000,
                    "tint": 99,
                },
            },
        ]
    }

    baseline = fit_train_median_baseline(manifest)

    assert baseline.exposure == 0.5
    assert baseline.temperature == 5500
    assert baseline.tint == 5
    assert baseline.fitted_samples == 2
