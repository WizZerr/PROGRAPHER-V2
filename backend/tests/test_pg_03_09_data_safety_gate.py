from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import pytest

from app.datasets.jpeg_integrity import (
    DATASET_SNAPSHOT_SCHEMA,
    DatasetSnapshotChangedError,
    JPEG_COLOR_CONTRACT_VERSION,
    JpegIntegrityError,
    WORKING_COLOR_SPACE,
    analyze_pair_geometry,
    freeze_dataset_snapshot,
    read_jpeg_working_rgb,
    sha256_file,
)
from app.evaluation.artifact_provenance import (
    J0_TARGET_FEATURE_CONTRACT_VERSION,
    RENDERER_CONTRACT_VERSION,
    target_bundle_provenance,
    target_semantics_sha256,
)
TRAINING_LAB = Path(__file__).resolve().parents[1] / "training_lab"
if str(TRAINING_LAB) not in sys.path:
    sys.path.insert(0, str(TRAINING_LAB))

from jpeg_j0_feasibility import RECIPE_VERSION
from jpeg_j1_synthetic_brain import IDENTITY_RECIPE
from jpeg_real_dataset_intake import _intake
import jpeg_real_j1_candidate as j1


CODE_REVISION = "a" * 40
DEPENDENCY_SHA = "b" * 64


def _scene(seed: int, width: int = 320, height: int = 220) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = xx / max(width - 1, 1)
    y = yy / max(height - 1, 1)

    image = np.zeros((height, width, 3), dtype=np.float32)
    image[:, :, 0] = 35 + 150 * x + 35 * (1 - y)
    image[:, :, 1] = 25 + 125 * y + 30 * x
    image[:, :, 2] = 45 + 110 * (1 - x) + 55 * y
    image = np.clip(image, 0, 255).astype(np.uint8)

    for index in range(28):
        center = (
            int(rng.integers(10, width - 10)),
            int(rng.integers(10, height - 10)),
        )
        radius = int(rng.integers(3, 12))
        color = tuple(
            int(value)
            for value in rng.integers(70, 255, size=3)
        )
        cv2.circle(image, center, radius, color, 2)

    cv2.putText(
        image,
        f"PG-{seed}",
        (18, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (250, 250, 250),
        2,
        cv2.LINE_AA,
    )
    return image


def _save_jpeg(path: Path, rgb: np.ndarray, quality: int = 96) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(
        path,
        format="JPEG",
        quality=quality,
    )


def _edited(rgb: np.ndarray, scale: float = 1.04, offset: float = 4.0) -> np.ndarray:
    return np.clip(
        rgb.astype(np.float32) * scale + offset,
        0,
        255,
    ).astype(np.uint8)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _pair(
    *,
    pair_id: str,
    split: str,
    original: Path,
    edited: Path,
) -> dict:
    return {
        "pair_id": pair_id,
        "event_id": f"event_{split}",
        "split": split,
        "usable_for_recipe_fit": True,
        "original_path": str(original.resolve()),
        "edited_path": str(edited.resolve()),
        "original_sha256": sha256_file(original),
        "edited_sha256": sha256_file(edited),
    }


def _target_from_pair(pair: dict) -> dict:
    return {
        "pair_id": pair["pair_id"],
        "event_id": pair["event_id"],
        "split": pair["split"],
        "original_path": pair["original_path"],
        "edited_path": pair["edited_path"],
        "original_sha256": pair["original_sha256"],
        "edited_sha256": pair["edited_sha256"],
        "recipe_version": RECIPE_VERSION,
        "recipe_transform": {
            "coefficients": IDENTITY_RECIPE.tolist(),
        },
        "j0_metrics": {
            "baseline_mae_255": 1.0,
            "reconstruction_mae_255": 0.5,
        },
    }


def _training_fixture(tmp_path: Path) -> dict:
    files: dict[str, tuple[Path, Path]] = {}
    pairs: list[dict] = []
    snapshot_entries: list[dict] = []

    for index, split in enumerate(("train", "validation", "test"), start=1):
        original = tmp_path / "photos" / split / "original.jpg"
        edited = tmp_path / "photos" / split / "edited.jpg"
        scene = _scene(800 + index)
        _save_jpeg(original, scene)
        _save_jpeg(edited, _edited(scene, 1.02 + index * 0.01, 3.0))

        pair = _pair(
            pair_id=f"pair-{split}",
            split=split,
            original=original,
            edited=edited,
        )
        pairs.append(pair)
        files[split] = (original, edited)

        for role, path, digest in (
            ("original", original, pair["original_sha256"]),
            ("edited", edited, pair["edited_sha256"]),
        ):
            stat = path.stat()
            snapshot_entries.append(
                {
                    "role": role,
                    "pair_id": pair["pair_id"],
                    "path": str(path.resolve()),
                    "size_bytes": int(stat.st_size),
                    "modified_ns": int(stat.st_mtime_ns),
                    "sha256": digest,
                }
            )

    snapshot = freeze_dataset_snapshot(snapshot_entries)
    assert snapshot["schema"] == DATASET_SNAPSHOT_SCHEMA
    snapshot_path = tmp_path / "dataset_snapshot.json"
    _write_json(snapshot_path, snapshot)

    dataset = {
        "schema_version": 1,
        "kind": "jpeg_real_event_dataset",
        "photographer_id": "photographer-fixture",
        "dataset_snapshot_path": str(snapshot_path.resolve()),
        "dataset_snapshot_id": snapshot["snapshot_id"],
        "working_color_space": WORKING_COLOR_SPACE,
        "color_contract_version": JPEG_COLOR_CONTRACT_VERSION,
        "cross_split_duplicates": [],
        "cross_split_source_groups": [],
        "unresolved_near_duplicate_suspects": [],
        "readiness": {
            "whole_event_train_validation_test_ready": True,
        },
        "pairs": pairs,
        "events": [
            {
                "event_id": pair["event_id"],
                "split": pair["split"],
                "usable_pairs": 1,
            }
            for pair in pairs
        ],
    }
    dataset_path = tmp_path / "dataset_manifest.json"
    _write_json(dataset_path, dataset)
    dataset_sha = sha256_file(dataset_path)

    target_payload = {
        "schema_version": 1,
        "kind": "jpeg_j0_recipe_targets",
        "created_at": "2026-10-04T00:00:00+00:00",
        "dataset_manifest_path": str(dataset_path.resolve()),
        "dataset_snapshot_id": snapshot["snapshot_id"],
        "photographer_id": "photographer-fixture",
        "split_mode": "train-validation",
        "test_unlocked": False,
        "targets": [
            _target_from_pair(pair)
            for pair in pairs
            if pair["split"] in {"train", "validation"}
        ],
    }
    target_payload["provenance"] = target_bundle_provenance(
        dataset_snapshot_id=snapshot["snapshot_id"],
        dataset_manifest_sha256=dataset_sha,
        target_semantics_sha256_value=target_semantics_sha256(target_payload),
        code_revision=CODE_REVISION,
        dependency_lock_sha256=DEPENDENCY_SHA,
        color_contract_version=JPEG_COLOR_CONTRACT_VERSION,
        feature_contract_version=J0_TARGET_FEATURE_CONTRACT_VERSION,
        recipe_contract_version=RECIPE_VERSION,
        renderer_contract_version=RENDERER_CONTRACT_VERSION,
        config={
            "max_edge": 1000,
            "preview_edge": 1200,
            "sample_pixels": 120000,
            "ridge_lambda": 1e-4,
            "jpeg_quality": 95,
            "aspect_tolerance": 0.01,
        },
        split_mode="train-validation",
    )
    targets_path = tmp_path / "recipe_targets.json"
    _write_json(targets_path, target_payload)

    return {
        "dataset": dataset,
        "dataset_path": dataset_path,
        "snapshot": snapshot,
        "snapshot_path": snapshot_path,
        "pairs": pairs,
        "files": files,
        "targets": target_payload,
        "targets_path": targets_path,
    }


def _rewrite_targets(
    fixture: dict,
    payload: dict,
    path: Path,
) -> Path:
    raw = dict(payload)
    raw.pop("provenance", None)
    raw["provenance"] = target_bundle_provenance(
        dataset_snapshot_id=fixture["snapshot"]["snapshot_id"],
        dataset_manifest_sha256=sha256_file(fixture["dataset_path"]),
        target_semantics_sha256_value=target_semantics_sha256(raw),
        code_revision=CODE_REVISION,
        dependency_lock_sha256=DEPENDENCY_SHA,
        color_contract_version=JPEG_COLOR_CONTRACT_VERSION,
        feature_contract_version=J0_TARGET_FEATURE_CONTRACT_VERSION,
        recipe_contract_version=RECIPE_VERSION,
        renderer_contract_version=RENDERER_CONTRACT_VERSION,
        config={
            "max_edge": 1000,
            "preview_edge": 1200,
            "sample_pixels": 120000,
            "ridge_lambda": 1e-4,
            "jpeg_quality": 95,
            "aspect_tolerance": 0.01,
        },
        split_mode=str(raw.get("split_mode") or "train-validation"),
    )
    _write_json(path, raw)
    return path


def test_pg_03_02_geometry_risk_is_fail_closed() -> None:
    original = _scene(101)
    cropped = original[28:-28, 42:-42]
    wrong_copy = _scene(9101)

    crop_evidence = analyze_pair_geometry(original, cropped)
    wrong_evidence = analyze_pair_geometry(original, wrong_copy)

    assert crop_evidence.usable is False
    assert crop_evidence.action in {
        "crop_same_ratio",
        "crop_or_geometry_mismatch",
        "wrong_copy_or_unverified",
    }
    assert wrong_evidence.usable is False
    assert wrong_evidence.action == "wrong_copy_or_unverified"


def test_pg_03_03_unsafe_color_encoding_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "cmyk-no-icc.jpg"
    Image.fromarray(_scene(102), mode="RGB").convert("CMYK").save(
        path,
        format="JPEG",
        quality=95,
    )

    with pytest.raises(
        JpegIntegrityError,
        match="missing_icc_for_non_rgb",
    ):
        read_jpeg_working_rgb(path)


def test_pg_03_04_mutated_dataset_stops_before_feature_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _training_fixture(tmp_path)
    train_original, _ = fixture["files"]["train"]
    train_original.write_bytes(
        train_original.read_bytes() + b"mutated-after-intake"
    )

    decode_calls: list[str] = []

    def forbidden_decode(path: str) -> np.ndarray:
        decode_calls.append(path)
        raise AssertionError("feature decode must not run after snapshot failure")

    monkeypatch.setattr(j1, "_decode_rgb", forbidden_decode)

    with pytest.raises(
        DatasetSnapshotChangedError,
        match="source_changed_size",
    ):
        j1._prepare_candidate_training(
            fixture["dataset_path"],
            fixture["targets_path"],
        )

    assert decode_calls == []


def test_pg_03_05_unapproved_identity_copy_is_not_learning_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "identity"
    original = root / "event_identity" / "ORIGINALS" / "IMG_0001.jpg"
    edited = root / "event_identity" / "EDITS" / "IMG_0001.jpg"
    _save_jpeg(original, _scene(103))
    edited.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, edited)

    payload = _intake(
        root=root,
        output=tmp_path / "identity-intake",
        photographer_id="photographer-fixture",
        aspect_tolerance=0.01,
        validation_events=[],
        test_events=[],
        rebuild_split_lock=False,
    )

    assert payload["pairs"][0]["status"] == "unchanged_unverified"
    assert payload["pairs"][0]["usable_for_recipe_fit"] is False
    assert payload["totals"]["approved_identity_pairs"] == 0


def test_pg_03_06_source_group_leakage_stops_before_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _training_fixture(tmp_path)
    dataset = json.loads(
        fixture["dataset_path"].read_text(encoding="utf-8")
    )
    dataset["cross_split_source_groups"] = [
        {
            "source_group_id": "sg-leak",
            "splits": ["train", "test"],
        }
    ]
    _write_json(fixture["dataset_path"], dataset)

    decode_calls: list[str] = []
    monkeypatch.setattr(
        j1,
        "_decode_rgb",
        lambda path: decode_calls.append(path),
    )

    with pytest.raises(
        ValueError,
        match="Source-group split leakage",
    ):
        j1._prepare_candidate_training(
            fixture["dataset_path"],
            fixture["targets_path"],
        )

    assert decode_calls == []


def test_pg_03_07_coverage_keeps_exclusions_visible(tmp_path: Path) -> None:
    root = tmp_path / "coverage"
    output = tmp_path / "coverage-intake"

    good = _scene(104)
    crop_source = _scene(105)

    _save_jpeg(
        root / "event_good" / "ORIGINALS" / "IMG_0001.jpg",
        good,
    )
    _save_jpeg(
        root / "event_good" / "EDITS" / "IMG_0001.jpg",
        _edited(good),
    )

    _save_jpeg(
        root / "event_crop" / "ORIGINALS" / "IMG_0001.jpg",
        crop_source,
    )
    _save_jpeg(
        root / "event_crop" / "EDITS" / "IMG_0001.jpg",
        _edited(crop_source)[30:-30, 45:-45],
    )

    payload = _intake(
        root=root,
        output=output,
        photographer_id="coverage-fixture",
        aspect_tolerance=0.01,
        validation_events=[],
        test_events=[],
        rebuild_split_lock=False,
    )
    coverage = json.loads(
        Path(payload["coverage_report_path"]).read_text(encoding="utf-8")
    )

    assert coverage["counts"]["matched_pairs"] == 2
    assert coverage["counts"]["usable_pairs"] == 1
    assert coverage["counts"]["excluded_pairs"] == 1
    assert coverage["coverage"]["exclusion_reasons"]
    assert coverage["hard_groups"]


def test_pg_03_08_target_tamper_stops_before_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _training_fixture(tmp_path)
    targets = json.loads(
        fixture["targets_path"].read_text(encoding="utf-8")
    )
    targets["targets"][0]["recipe_transform"]["coefficients"][0][0] = 99.0
    _write_json(fixture["targets_path"], targets)

    decode_calls: list[str] = []
    monkeypatch.setattr(
        j1,
        "_decode_rgb",
        lambda path: decode_calls.append(path),
    )

    with pytest.raises(
        ValueError,
        match="semantic content hash",
    ):
        j1._prepare_candidate_training(
            fixture["dataset_path"],
            fixture["targets_path"],
        )

    assert decode_calls == []


def test_locked_test_target_contamination_is_rejected_before_any_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _training_fixture(tmp_path)
    targets = json.loads(
        fixture["targets_path"].read_text(encoding="utf-8")
    )
    targets.pop("provenance", None)
    test_pair = next(
        pair for pair in fixture["pairs"] if pair["split"] == "test"
    )
    targets["targets"].append(_target_from_pair(test_pair))
    contaminated_path = _rewrite_targets(
        fixture,
        targets,
        tmp_path / "contaminated_targets.json",
    )

    decode_calls: list[str] = []

    def forbidden_decode(path: str) -> np.ndarray:
        decode_calls.append(path)
        raise AssertionError("no image may decode before Test contamination is rejected")

    monkeypatch.setattr(j1, "_decode_rgb", forbidden_decode)

    with pytest.raises(
        ValueError,
        match="locked Test targets",
    ):
        j1._prepare_candidate_training(
            fixture["dataset_path"],
            contaminated_path,
        )

    assert decode_calls == []


def test_candidate_training_reads_train_validation_but_never_test_pixels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _training_fixture(tmp_path)
    original_decode = j1._decode_rgb
    decoded: list[str] = []

    def recording_decode(path: str) -> np.ndarray:
        decoded.append(str(Path(path).resolve()))
        return original_decode(path)

    monkeypatch.setattr(j1, "_decode_rgb", recording_decode)

    _, _, _, _, rows = j1._prepare_candidate_training(
        fixture["dataset_path"],
        fixture["targets_path"],
    )

    decoded_set = set(decoded)
    test_original, _ = fixture["files"]["test"]

    assert {row["split"] for row in rows} == {"train", "validation"}
    assert str(test_original.resolve()) not in decoded_set
    assert all("/test/" not in value.replace("\\", "/") for value in decoded_set)


def test_unresolved_near_duplicate_stops_before_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _training_fixture(tmp_path)
    dataset = json.loads(
        fixture["dataset_path"].read_text(encoding="utf-8")
    )
    dataset["unresolved_near_duplicate_suspects"] = [
        {"review_id": "suspect-001"}
    ]
    _write_json(fixture["dataset_path"], dataset)

    decode_calls: list[str] = []
    monkeypatch.setattr(
        j1,
        "_decode_rgb",
        lambda path: decode_calls.append(path),
    )

    with pytest.raises(
        ValueError,
        match="Unresolved near-duplicate suspects",
    ):
        j1._prepare_candidate_training(
            fixture["dataset_path"],
            fixture["targets_path"],
        )

    assert decode_calls == []
