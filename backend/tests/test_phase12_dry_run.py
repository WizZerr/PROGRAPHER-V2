from __future__ import annotations

from app.brain_v2.training.dry_run import (
    build_synthetic_manifest,
    build_synthetic_split,
    run_phase12_synthetic_dry_run,
)


def test_synthetic_fixture_has_event_safe_cohorts() -> None:
    manifest = build_synthetic_manifest()
    split = build_synthetic_split(manifest)

    assert manifest.event_count == 3
    assert split.train_sample_count == 4
    assert split.validation_sample_count == 2
    assert set(split.train_event_ids).isdisjoint(
        set(split.validation_event_ids)
    )


def test_end_to_end_dry_run_completes() -> None:
    report = run_phase12_synthetic_dry_run()

    assert report["assertions"] == {
        "dataset_identity_connected": True,
        "split_identity_connected": True,
        "train_only_baseline_fitting": True,
        "validation_only_predictions": True,
        "evaluation_completed": True,
    }


def test_end_to_end_dry_run_is_deterministic() -> None:
    first = run_phase12_synthetic_dry_run()
    second = run_phase12_synthetic_dry_run()

    assert first["baseline"]["baseline_id"] == second["baseline"]["baseline_id"]
    assert (
        first["experiment"]["experiment_id"]
        == second["experiment"]["experiment_id"]
    )
    assert (
        first["evaluation"]["evaluation_id"]
        == second["evaluation"]["evaluation_id"]
    )


def test_synthetic_dry_run_forbids_quality_claim() -> None:
    report = run_phase12_synthetic_dry_run()

    assert report["fixture_kind"] == "synthetic_only"
    assert report["quality_claim_allowed"] is False
    assert "not a photographic-quality result" in report["warning"]
