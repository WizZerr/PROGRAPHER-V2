from __future__ import annotations

from pathlib import Path

import pytest

from app.evaluation.artifact_provenance import (
    FEATURE_CONTRACT_VERSION,
    J0_TARGET_FEATURE_CONTRACT_VERSION,
    RENDERER_CONTRACT_VERSION,
    candidate_provenance,
    canonical_json_sha256,
    ensure_immutable_artifact_dir,
    target_bundle_provenance,
    target_semantics_sha256,
    verify_candidate_provenance,
    verify_file_manifest,
    verify_target_bundle_for_candidate,
    build_file_manifest,
    write_immutable_json,
)


REV_A = "a" * 40
REV_B = "b" * 40
DATASET_SHA = "1" * 64
SNAPSHOT_ID = "2" * 64
DEPENDENCY_SHA = "3" * 64
COLOR_VERSION = "jpeg-color-exif-icc-srgb-v1"
RECIPE_VERSION = "jpeg-recipe-j0-polynomial-v1"


def _target_payload(
    *,
    created_at: str = "2026-10-04T00:00:00+00:00",
    dataset_path: str = "/first/location/dataset_manifest.json",
    coefficient: float = 1.0,
) -> dict:
    return {
        "schema_version": 1,
        "kind": "jpeg_j0_recipe_targets",
        "created_at": created_at,
        "dataset_manifest_path": dataset_path,
        "dataset_snapshot_id": SNAPSHOT_ID,
        "photographer_id": "photographer-01",
        "split_mode": "train-validation",
        "test_unlocked": False,
        "targets": [
            {
                "pair_id": "pair-01",
                "event_id": "event-01",
                "split": "train",
                "original_path": "/some/original.jpg",
                "edited_path": "/some/edited.jpg",
                "original_sha256": "4" * 64,
                "edited_sha256": "5" * 64,
                "recipe_version": RECIPE_VERSION,
                "recipe_transform": {
                    "coefficients": [[coefficient, 0.0, 0.0]]
                },
                "j0_metrics": {
                    "reconstruction_mae_255": 1.25,
                },
            }
        ],
    }


def _target_provenance(
    payload: dict,
    *,
    code_revision: str = REV_A,
    dependency_sha: str = DEPENDENCY_SHA,
    color_version: str = COLOR_VERSION,
    feature_version: str = J0_TARGET_FEATURE_CONTRACT_VERSION,
    renderer_version: str = RENDERER_CONTRACT_VERSION,
    ridge_lambda: float = 0.001,
) -> dict:
    return target_bundle_provenance(
        dataset_snapshot_id=SNAPSHOT_ID,
        dataset_manifest_sha256=DATASET_SHA,
        target_semantics_sha256_value=target_semantics_sha256(payload),
        code_revision=code_revision,
        dependency_lock_sha256=dependency_sha,
        color_contract_version=color_version,
        feature_contract_version=feature_version,
        recipe_contract_version=RECIPE_VERSION,
        renderer_contract_version=renderer_version,
        config={
            "ridge_lambda": ridge_lambda,
            "max_edge": 1000,
        },
        split_mode="train-validation",
    )


def _candidate(
    *,
    code_revision: str = REV_A,
    dependency_sha: str = DEPENDENCY_SHA,
    color_version: str = COLOR_VERSION,
    feature_version: str = FEATURE_CONTRACT_VERSION,
    renderer_version: str = RENDERER_CONTRACT_VERSION,
    ridge_lambda: float = 0.02,
    target_semantic_sha: str = "6" * 64,
    target_file_sha: str = "7" * 64,
) -> dict:
    return candidate_provenance(
        candidate_family="measured_features_ridge",
        model_version="jpeg-j1-real-measured-features-ridge-v1",
        dataset_snapshot_id=SNAPSHOT_ID,
        dataset_manifest_sha256=DATASET_SHA,
        target_artifact_id="targets-" + "8" * 24,
        target_semantics_sha256_value=target_semantic_sha,
        target_artifact_sha256=target_file_sha,
        code_revision=code_revision,
        dependency_lock_sha256=dependency_sha,
        color_contract_version=color_version,
        feature_contract_version=feature_version,
        feature_names=["bias", "mean_r", "mean_g"],
        recipe_contract_version=RECIPE_VERSION,
        renderer_contract_version=renderer_version,
        config={
            "ridge_lambda": ridge_lambda,
            "standardization": "train-zscore-except-bias-v1",
        },
    )


def test_target_identity_ignores_timestamp_and_locator_noise() -> None:
    first = _target_payload()
    moved = _target_payload(
        created_at="2030-01-01T12:34:56+00:00",
        dataset_path="D:/moved/dataset_manifest.json",
    )
    moved["targets"][0]["original_path"] = "D:/moved/original.jpg"
    moved["targets"][0]["edited_path"] = "D:/moved/edited.jpg"
    moved["targets"][0]["j0_metrics"]["reconstruction_mae_255"] = 9.99

    assert target_semantics_sha256(first) == target_semantics_sha256(moved)
    assert (
        _target_provenance(first)["artifact_id"]
        == _target_provenance(moved)["artifact_id"]
    )


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("code_revision", REV_B),
        ("dependency_sha", "9" * 64),
        ("color_version", "jpeg-color-v2"),
        ("feature_version", "jpeg-j0-features-v2"),
        ("renderer_version", "jpeg-renderer-v2"),
        ("ridge_lambda", 0.123),
    ],
)
def test_material_target_contract_change_creates_new_id(
    change: str,
    value: object,
) -> None:
    payload = _target_payload()
    baseline = _target_provenance(payload)
    kwargs = {change: value}
    changed = _target_provenance(payload, **kwargs)

    assert baseline["artifact_id"] != changed["artifact_id"]


def test_target_recipe_change_creates_new_id_and_tamper_is_rejected() -> None:
    first = _target_payload(coefficient=1.0)
    second = _target_payload(coefficient=1.1)

    assert (
        _target_provenance(first)["artifact_id"]
        != _target_provenance(second)["artifact_id"]
    )

    payload = _target_payload()
    payload["provenance"] = _target_provenance(payload)
    verified = verify_target_bundle_for_candidate(
        target_payload=payload,
        dataset_snapshot_id=SNAPSHOT_ID,
        dataset_manifest_sha256=DATASET_SHA,
    )
    assert verified["artifact_id"].startswith("targets-")

    payload["targets"][0]["recipe_transform"]["coefficients"][0][0] = 9.0
    with pytest.raises(
        ValueError,
        match="semantic content hash",
    ):
        verify_target_bundle_for_candidate(
            target_payload=payload,
            dataset_snapshot_id=SNAPSHOT_ID,
            dataset_manifest_sha256=DATASET_SHA,
        )


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("code_revision", REV_B),
        ("dependency_sha", "9" * 64),
        ("color_version", "jpeg-color-v2"),
        ("feature_version", "jpeg-features-v2"),
        ("renderer_version", "jpeg-renderer-v2"),
        ("ridge_lambda", 0.21),
        ("target_semantic_sha", "f" * 64),
    ],
)
def test_material_candidate_change_creates_new_candidate_id(
    change: str,
    value: object,
) -> None:
    baseline = _candidate()
    changed = _candidate(**{change: value})

    assert baseline["artifact_id"] != changed["artifact_id"]


def test_nonsemantic_target_file_bytes_do_not_change_candidate_id() -> None:
    first = _candidate(target_file_sha="1" * 64)
    second = _candidate(target_file_sha="2" * 64)

    assert first["artifact_id"] == second["artifact_id"]
    assert (
        first["evidence"]["target_artifact_sha256"]
        != second["evidence"]["target_artifact_sha256"]
    )


def test_candidate_provenance_self_verifies() -> None:
    provenance = _candidate()
    assert (
        verify_candidate_provenance(provenance)["artifact_id"]
        == provenance["artifact_id"]
    )

    corrupted = {
        **provenance,
        "artifact_id": "candidate-" + "0" * 24,
    }
    with pytest.raises(ValueError, match="artifact id"):
        verify_candidate_provenance(corrupted)


def test_immutable_artifact_directory_refuses_overwrite(
    tmp_path: Path,
) -> None:
    root = tmp_path / "candidates"
    artifact_id = _candidate()["artifact_id"]

    first = ensure_immutable_artifact_dir(root, artifact_id)
    assert first.is_dir()

    with pytest.raises(FileExistsError, match="Immutable artifact"):
        ensure_immutable_artifact_dir(root, artifact_id)


def test_candidate_file_manifest_detects_byte_tampering(
    tmp_path: Path,
) -> None:
    candidate = ensure_immutable_artifact_dir(
        tmp_path / "candidates",
        _candidate()["artifact_id"],
    )
    model = candidate / "model" / "model.npz"
    contract = candidate / "model" / "model_contract.json"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_bytes(b"model-v1")
    contract.write_text('{"version":1}', encoding="utf-8")

    manifest = build_file_manifest(
        candidate,
        ["model/model.npz", "model/model_contract.json"],
        candidate_id=candidate.name,
    )
    write_immutable_json(
        candidate / "artifact_manifest.json",
        manifest,
    )

    verify_file_manifest(
        candidate,
        manifest,
        expected_candidate_id=candidate.name,
    )

    model.write_bytes(b"model-v2-tampered")
    with pytest.raises(
        ValueError,
        match="candidate artifact",
    ):
        verify_file_manifest(
            candidate,
            manifest,
            expected_candidate_id=candidate.name,
        )


def test_canonical_config_hash_is_key_order_independent() -> None:
    assert canonical_json_sha256(
        {"a": 1, "b": {"x": 2, "y": 3}}
    ) == canonical_json_sha256(
        {"b": {"y": 3, "x": 2}, "a": 1}
    )
