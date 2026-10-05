from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageCms
import pytest

from app.datasets.source_groups import (
    SourceAsset,
    build_source_groups,
    load_near_duplicate_reviews,
    source_asset_id,
)
from app.datasets.jpeg_integrity import (
    DatasetSnapshotChangedError,
    JpegIntegrityError,
    WORKING_COLOR_SPACE,
    analyze_edit_scope,
    analyze_pair_geometry,
    load_and_validate_dataset_snapshot,
    read_jpeg_working_rgb,
)
from training_lab.jpeg_j0_feasibility import run as run_j0
from training_lab.jpeg_real_dataset_intake import _intake


def _scene(seed: int, width: int = 480, height: int = 320) -> np.ndarray:
    rng = np.random.default_rng(seed)
    image = np.zeros((height, width, 3), dtype=np.uint8)

    x = np.linspace(20, 230, width, dtype=np.uint8)
    y = np.linspace(220, 30, height, dtype=np.uint8)
    image[:, :, 0] = x[None, :]
    image[:, :, 1] = y[:, None]
    image[:, :, 2] = rng.integers(
        0,
        100,
        size=(height, width),
        dtype=np.uint8,
    )

    for index in range(45):
        center = (
            int(rng.integers(15, width - 15)),
            int(rng.integers(15, height - 15)),
        )
        radius = int(rng.integers(4, 16))
        color = tuple(
            int(value)
            for value in rng.integers(80, 255, size=3)
        )
        cv2.circle(image, center, radius, color, 2)

        if index % 4 == 0:
            start = (
                int(rng.integers(0, width)),
                int(rng.integers(0, height)),
            )
            end = (
                int(rng.integers(0, width)),
                int(rng.integers(0, height)),
            )
            cv2.line(image, start, end, color, 2)

    cv2.putText(
        image,
        f"event-{seed}",
        (24, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return image


def _save_jpeg(
    path: Path,
    rgb: np.ndarray,
    *,
    orientation: int | None = None,
    embed_srgb_icc: bool = False,
    camera_make: str | None = None,
    camera_model: str | None = None,
    iso: int | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(rgb, mode="RGB")

    kwargs: dict = {"format": "JPEG", "quality": 98}
    if (
        orientation is not None
        or camera_make is not None
        or camera_model is not None
        or iso is not None
    ):
        exif = image.getexif()
        if orientation is not None:
            exif[274] = orientation
        if camera_make is not None:
            exif[271] = camera_make
        if camera_model is not None:
            exif[272] = camera_model
        if iso is not None:
            exif[34855] = int(iso)
        kwargs["exif"] = exif

    if embed_srgb_icc:
        profile = ImageCms.ImageCmsProfile(
            ImageCms.createProfile("sRGB")
        )
        kwargs["icc_profile"] = profile.tobytes()

    image.save(path, **kwargs)


def _save_mpo_jpeg(path: Path, rgb: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    primary = Image.fromarray(rgb, mode="RGB")
    auxiliary = Image.fromarray(
        np.flip(rgb, axis=1).copy(),
        mode="RGB",
    )
    primary.save(
        path,
        format="MPO",
        save_all=True,
        append_images=[auxiliary],
        quality=98,
    )


def test_jpeg_decoder_accepts_mpo_primary_frame(tmp_path: Path) -> None:
    source = _scene(9, width=360, height=240)
    path = tmp_path / "camera-mpf.JPG"
    _save_mpo_jpeg(path, source)

    with Image.open(path) as opened:
        assert opened.format == "MPO"
        assert getattr(opened, "n_frames", 1) >= 2

    decoded, evidence = read_jpeg_working_rgb(path)

    assert decoded.shape == source.shape
    assert evidence.display_width == source.shape[1]
    assert evidence.display_height == source.shape[0]
    assert evidence.color_action == "assume_srgb_no_icc"
    assert evidence.working_color_space == WORKING_COLOR_SPACE


def test_jpeg_decoder_normalizes_exif_and_icc(tmp_path: Path) -> None:
    source = _scene(10, width=420, height=280)

    oriented = tmp_path / "oriented.jpg"
    _save_jpeg(
        oriented,
        source,
        orientation=6,
        embed_srgb_icc=True,
    )

    decoded, evidence = read_jpeg_working_rgb(oriented)

    assert evidence.exif_orientation == 6
    assert evidence.icc_present is True
    assert evidence.icc_sha256
    assert evidence.color_action == "icc_to_srgb"
    assert evidence.working_color_space == WORKING_COLOR_SPACE

    # EXIF orientation 6 displays the stored landscape JPEG as portrait.
    assert decoded.shape[0] == evidence.display_height
    assert decoded.shape[1] == evidence.display_width
    assert evidence.display_width == evidence.stored_height
    assert evidence.display_height == evidence.stored_width


def test_jpeg_decoder_records_explicit_missing_icc_assumption(
    tmp_path: Path,
) -> None:
    source = tmp_path / "plain.jpg"
    _save_jpeg(source, _scene(11))

    _, evidence = read_jpeg_working_rgb(source)

    assert evidence.icc_present is False
    assert evidence.color_action == "assume_srgb_no_icc"
    assert evidence.working_color_space == WORKING_COLOR_SPACE


def test_decoder_records_camera_and_lighting_metadata(
    tmp_path: Path,
) -> None:
    dark = np.clip(
        _scene(14).astype(np.float32) * 0.18,
        0,
        255,
    ).astype(np.uint8)
    path = tmp_path / "camera-dark.jpg"
    _save_jpeg(
        path,
        dark,
        camera_make="Sony",
        camera_model="ILCE-7M4",
        iso=3200,
    )

    _, evidence = read_jpeg_working_rgb(path)

    assert evidence.camera_make == "Sony"
    assert evidence.camera_model == "ILCE-7M4"
    assert evidence.iso == 3200
    assert evidence.lighting_bucket == "low_key"
    assert evidence.mean_luma < 0.28
    assert evidence.perceptual_hash64


def test_edit_scope_distinguishes_global_from_local_or_complex() -> None:
    original = _scene(15)

    global_edit = np.clip(
        original.astype(np.float32) * 1.08 + 6.0,
        0,
        255,
    ).astype(np.uint8)
    global_evidence = analyze_edit_scope(
        original,
        global_edit,
    )
    assert global_evidence.scope == "global_like"
    assert global_evidence.affine_residual_p90_255 <= 8.0

    local_edit = original.copy()
    local_edit[80:240, 120:360] = np.clip(
        local_edit[80:240, 120:360].astype(np.float32) * 0.55 + 60.0,
        0,
        255,
    ).astype(np.uint8)
    local_evidence = analyze_edit_scope(
        original,
        local_edit,
    )
    assert local_evidence.scope == "local_or_complex_suspected"
    assert local_evidence.affine_residual_p90_255 > 8.0


def test_srgb_icc_and_missing_icc_reach_same_working_space(
    tmp_path: Path,
) -> None:
    source = _scene(12)
    without_icc = tmp_path / "without-icc.jpg"
    with_icc = tmp_path / "with-icc.jpg"

    _save_jpeg(without_icc, source)
    _save_jpeg(with_icc, source, embed_srgb_icc=True)

    plain_rgb, plain_evidence = read_jpeg_working_rgb(without_icc)
    tagged_rgb, tagged_evidence = read_jpeg_working_rgb(with_icc)

    assert plain_evidence.working_color_space == WORKING_COLOR_SPACE
    assert tagged_evidence.working_color_space == WORKING_COLOR_SPACE
    assert plain_evidence.color_action == "assume_srgb_no_icc"
    assert tagged_evidence.color_action == "icc_to_srgb"

    mae = float(
        np.abs(
            plain_rgb.astype(np.float32)
            - tagged_rgb.astype(np.float32)
        ).mean()
    )
    assert mae < 3.0


def test_missing_icc_non_rgb_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "cmyk-without-icc.jpg"
    rgb = _scene(13)
    Image.fromarray(rgb, mode="RGB").convert("CMYK").save(
        path,
        format="JPEG",
        quality=95,
    )

    with pytest.raises(
        JpegIntegrityError,
        match="missing_icc_for_non_rgb",
    ):
        read_jpeg_working_rgb(path)


def test_geometry_contract_blocks_rotation_mirror_crop_and_wrong_copy() -> None:
    original = _scene(20)
    edited = np.clip(
        original.astype(np.float32) * 1.04 + 3.0,
        0,
        255,
    ).astype(np.uint8)

    same = analyze_pair_geometry(original, edited)
    assert same.usable is True
    assert same.action == "same_dimensions"

    resized = analyze_pair_geometry(
        original,
        cv2.resize(edited, (240, 160), interpolation=cv2.INTER_AREA),
    )
    assert resized.usable is True
    assert resized.action == "resize_only"

    rotated = analyze_pair_geometry(
        original,
        cv2.rotate(edited, cv2.ROTATE_90_CLOCKWISE),
    )
    assert rotated.usable is False
    assert rotated.action == "rotation_mismatch"

    mirrored = analyze_pair_geometry(
        original,
        cv2.flip(edited, 1),
    )
    assert mirrored.usable is False
    assert mirrored.action in {
        "mirror_mismatch",
        "wrong_copy_or_unverified",
    }

    cropped = analyze_pair_geometry(
        original,
        edited[32:-32, 48:-48],
    )
    assert cropped.usable is False
    assert cropped.action in {
        "crop_same_ratio",
        "crop_or_geometry_mismatch",
    }

    wrong = analyze_pair_geometry(
        original,
        _scene(999),
    )
    assert wrong.usable is False
    assert wrong.action == "wrong_copy_or_unverified"


def test_intake_coverage_separates_file_counts_from_usable_pairs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "coverage-dataset"
    output = tmp_path / "coverage-output"

    for index, seed in enumerate((501, 777, 999), start=1):
        event_id = f"event_{index}"
        original = _scene(seed)
        original_path = root / event_id / "ORIGINALS" / "IMG_0001.jpg"
        edited_path = root / event_id / "EDITS" / "IMG_0001.jpg"
        _save_jpeg(
            original_path,
            original,
            camera_make="Canon" if index < 3 else "Sony",
            camera_model="R6" if index < 3 else "ILCE-7M4",
            iso=800 * index,
        )

        if index == 2:
            edited = np.clip(
                original.astype(np.float32) * 1.05 + 5.0,
                0,
                255,
            ).astype(np.uint8)
            edited = edited[40:-40, 70:-70]
        elif index == 3:
            edited = original.copy()
            edited[70:250, 110:370] = np.clip(
                edited[70:250, 110:370].astype(np.float32) * 0.60 + 50.0,
                0,
                255,
            ).astype(np.uint8)
        else:
            edited = np.clip(
                original.astype(np.float32) * 1.06 + 4.0,
                0,
                255,
            ).astype(np.uint8)

        _save_jpeg(edited_path, edited)

    payload = _intake(
        root=root,
        output=output,
        photographer_id="coverage-photographer",
        aspect_tolerance=0.01,
        validation_events=[],
        test_events=[],
        rebuild_split_lock=False,
    )

    coverage_path = Path(payload["coverage_report_path"])
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))

    assert coverage["counts"]["original_files"] == 3
    assert coverage["counts"]["edited_files"] == 3
    assert coverage["counts"]["matched_pairs"] == 3
    assert coverage["counts"]["usable_pairs"] == 2
    assert coverage["counts"]["excluded_pairs"] == 1

    assert coverage["coverage"]["camera_models"]["Canon|R6"] == 1
    assert coverage["coverage"]["camera_models"]["Sony|ILCE-7M4"] == 1
    assert coverage["coverage"]["edit_scopes"]["global_like"] >= 1
    assert (
        coverage["coverage"]["edit_scopes"]["local_or_complex_suspected"]
        >= 1
    )
    assert any(
        reason in coverage["coverage"]["exclusion_reasons"]
        for reason in {"crop_same_ratio", "crop_or_geometry_mismatch"}
    )
    assert coverage["hard_groups"]
    assert payload["readiness"]["coverage_report_generated"] is True


def test_identity_target_requires_explicit_approval_and_reaches_j0(
    tmp_path: Path,
) -> None:
    root = tmp_path / "identity-dataset"
    originals = root / "event_identity" / "ORIGINALS"
    edits = root / "event_identity" / "EDITS"

    original_path = originals / "IMG_0001.jpg"
    edited_path = edits / "IMG_0001.jpg"
    _save_jpeg(original_path, _scene(40))
    edited_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original_path, edited_path)

    unapproved = _intake(
        root=root,
        output=tmp_path / "identity-unapproved",
        photographer_id="fixture-photographer",
        aspect_tolerance=0.01,
        validation_events=[],
        test_events=[],
        rebuild_split_lock=False,
    )

    unapproved_pair = unapproved["pairs"][0]
    assert unapproved_pair["status"] == "unchanged_unverified"
    assert unapproved_pair["usable_for_recipe_fit"] is False
    assert unapproved_pair["identity_target_approved"] is False
    assert unapproved["totals"]["approved_identity_pairs"] == 0
    assert unapproved["totals"]["unverified_identity_pairs"] == 1

    approvals_path = tmp_path / "identity-approvals.json"
    approvals_path.write_text(
        json.dumps(
            {
                "schema": "prographer.identity-approvals.v1",
                "photographer_id": "fixture-photographer",
                "approvals": [
                    {
                        "event_id": "event_identity",
                        "original_relative_path": "IMG_0001.jpg",
                        "decision": "approved_unchanged_final",
                        "approved_by": "fixture-photographer",
                        "approved_at": "2026-10-04T00:00:00Z",
                        "note": "Photographer confirmed final needs no edit.",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    approved = _intake(
        root=root,
        output=tmp_path / "identity-approved",
        photographer_id="fixture-photographer",
        aspect_tolerance=0.01,
        validation_events=[],
        test_events=[],
        rebuild_split_lock=False,
        identity_approvals_path=approvals_path,
    )

    approved_pair = approved["pairs"][0]
    assert approved_pair["status"] == "identity_approved"
    assert approved_pair["usable_for_recipe_fit"] is True
    assert approved_pair["identity_target_approved"] is True
    assert approved_pair["identity_approval_by"] == "fixture-photographer"
    assert approved["totals"]["approved_identity_pairs"] == 1
    assert approved["totals"]["unverified_identity_pairs"] == 0
    assert approved["identity_approvals_sha256"]

    j0_manifest = Path(approved["events"][0]["j0_manifest_path"])
    manifest_payload = json.loads(
        j0_manifest.read_text(encoding="utf-8")
    )
    assert manifest_payload["pairs"][0]["identity_target_approved"] is True
    assert manifest_payload["pairs"][0]["target_kind"] == "identity"

    j0 = run_j0(
        manifest_path=j0_manifest,
        output_root=tmp_path / "identity-j0",
        max_edge=360,
        preview_edge=360,
        sample_pixels=3000,
        ridge_lambda=1e-6,
        aspect_tolerance=0.01,
        jpeg_quality=95,
        limit=None,
    )
    assert j0["pairs_completed"] == 1
    assert j0["pairs_skipped"] == 0

    # The same approval is no longer valid if the edited bytes later diverge.
    changed = np.clip(
        _scene(40).astype(np.float32) * 0.92,
        0,
        255,
    ).astype(np.uint8)
    _save_jpeg(edited_path, changed)

    with pytest.raises(
        ValueError,
        match="Identity approval is stale",
    ):
        _intake(
            root=root,
            output=tmp_path / "identity-stale",
            photographer_id="fixture-photographer",
            aspect_tolerance=0.01,
            validation_events=[],
            test_events=[],
            rebuild_split_lock=False,
            identity_approvals_path=approvals_path,
        )


def test_source_groups_link_recompressed_resize_but_not_unrelated(
    tmp_path: Path,
) -> None:
    source_a = tmp_path / "source-a.jpg"
    source_b = tmp_path / "source-b-resized.jpg"
    source_c = tmp_path / "source-c.jpg"

    scene = _scene(60)
    _save_jpeg(source_a, scene)

    resized = cv2.resize(
        scene,
        (360, 240),
        interpolation=cv2.INTER_AREA,
    )
    Image.fromarray(resized, mode="RGB").save(
        source_b,
        format="JPEG",
        quality=84,
    )
    _save_jpeg(source_c, _scene(880))

    assets: list[SourceAsset] = []
    for event_id, path in (
        ("event_a", source_a),
        ("event_b", source_b),
        ("event_c", source_c),
    ):
        _, evidence = read_jpeg_working_rgb(path)
        digest = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
        relative = path.name
        assets.append(
            SourceAsset(
                source_id=source_asset_id(event_id, relative, digest),
                event_id=event_id,
                relative_path=relative,
                path=str(path),
                sha256=digest,
                perceptual_hash64=evidence.perceptual_hash64,
            )
        )

    analysis = build_source_groups(assets)

    grouped_events = [
        set(group["event_ids"])
        for group in analysis["groups"]
    ]
    assert {"event_a", "event_b"} in grouped_events
    assert {"event_c"} in grouped_events
    assert any(
        relation["relation"] == "verified_near_duplicate"
        for relation in analysis["relations"]
    )
    assert analysis["unresolved_suspects"] == []


def test_near_duplicate_suspect_requires_explicit_human_review(
    tmp_path: Path,
) -> None:
    left_path = tmp_path / "left.jpg"
    right_path = tmp_path / "right.jpg"
    _save_jpeg(left_path, _scene(61))
    _save_jpeg(right_path, _scene(999))

    left_sha = __import__("hashlib").sha256(left_path.read_bytes()).hexdigest()
    right_sha = __import__("hashlib").sha256(right_path.read_bytes()).hexdigest()

    # Force both assets into the perceptual shortlist. Geometry must still
    # refuse to silently group unrelated photos.
    shared_candidate_hash = "0f0f0f0f0f0f0f0f"
    assets = [
        SourceAsset(
            source_id=source_asset_id("event_left", "left.jpg", left_sha),
            event_id="event_left",
            relative_path="left.jpg",
            path=str(left_path),
            sha256=left_sha,
            perceptual_hash64=shared_candidate_hash,
        ),
        SourceAsset(
            source_id=source_asset_id("event_right", "right.jpg", right_sha),
            event_id="event_right",
            relative_path="right.jpg",
            path=str(right_path),
            sha256=right_sha,
            perceptual_hash64=shared_candidate_hash,
        ),
    ]

    unresolved = build_source_groups(assets)
    assert len(unresolved["unresolved_suspects"]) == 1
    review_id = unresolved["unresolved_suspects"][0]["review_id"]

    reviews_path = tmp_path / "near-duplicate-reviews.json"
    reviews_path.write_text(
        json.dumps(
            {
                "schema": "prographer.near-duplicate-reviews.v1",
                "photographer_id": "fixture-photographer",
                "reviews": [
                    {
                        "review_id": review_id,
                        "decision": "distinct_source",
                        "reviewed_by": "fixture-photographer",
                        "reviewed_at": "2026-10-04T00:00:00Z",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    reviews, review_sha = load_near_duplicate_reviews(
        reviews_path,
        photographer_id="fixture-photographer",
    )
    resolved = build_source_groups(assets, reviews=reviews)

    assert review_sha
    assert resolved["unresolved_suspects"] == []
    assert len(resolved["groups"]) == 2
    assert any(
        relation["relation"] == "human_review"
        and relation["review_decision"] == "distinct_source"
        for relation in resolved["relations"]
    )


def test_intake_keeps_near_duplicate_events_in_one_split_and_new_event_unassigned(
    tmp_path: Path,
) -> None:
    root = tmp_path / "grouped-dataset"
    output = tmp_path / "grouped-intake"

    originals_by_event: dict[str, np.ndarray] = {
        "event_1": _scene(70),
        "event_3": _scene(170),
        "event_4": _scene(270),
    }
    originals_by_event["event_2"] = cv2.resize(
        originals_by_event["event_1"],
        (360, 240),
        interpolation=cv2.INTER_AREA,
    )

    for event_id, original in originals_by_event.items():
        originals = root / event_id / "ORIGINALS"
        edits = root / event_id / "EDITS"
        _save_jpeg(originals / "IMG_0001.jpg", original)
        edited = np.clip(
            original.astype(np.float32) * 1.03 + 5.0,
            0,
            255,
        ).astype(np.uint8)
        _save_jpeg(edits / "IMG_0001.jpg", edited)

    first = _intake(
        root=root,
        output=output,
        photographer_id="fixture-photographer",
        aspect_tolerance=0.01,
        validation_events=[],
        test_events=[],
        rebuild_split_lock=False,
    )

    splits = {
        event["event_id"]: event["split"]
        for event in first["events"]
    }
    assert splits["event_1"] == splits["event_2"]
    assert first["totals"]["cross_event_source_groups"] >= 1
    assert first["totals"]["verified_near_duplicate_relations"] >= 1
    assert first["totals"]["cross_split_source_group_leaks"] == 0
    assert first["readiness"]["source_group_split_leakage_clear"] is True
    assert first["readiness"]["whole_event_train_validation_test_ready"] is True

    locked_test_events = {
        event_id
        for event_id, split in splits.items()
        if split == "test"
    }
    assert locked_test_events

    event_5_original = _scene(370)
    _save_jpeg(
        root / "event_5" / "ORIGINALS" / "IMG_0001.jpg",
        event_5_original,
    )
    _save_jpeg(
        root / "event_5" / "EDITS" / "IMG_0001.jpg",
        np.clip(
            event_5_original.astype(np.float32) * 1.04 + 3.0,
            0,
            255,
        ).astype(np.uint8),
    )

    second = _intake(
        root=root,
        output=output,
        photographer_id="fixture-photographer",
        aspect_tolerance=0.01,
        validation_events=[],
        test_events=[],
        rebuild_split_lock=False,
    )
    second_splits = {
        event["event_id"]: event["split"]
        for event in second["events"]
    }

    assert second_splits["event_5"] == "unassigned"
    for event_id in locked_test_events:
        assert second_splits[event_id] == "test"


def test_explicit_split_refuses_to_separate_one_source_group(
    tmp_path: Path,
) -> None:
    root = tmp_path / "explicit-group-dataset"
    base = _scene(71)

    for event_id, original in (
        ("event_1", base),
        (
            "event_2",
            cv2.resize(
                base,
                (360, 240),
                interpolation=cv2.INTER_AREA,
            ),
        ),
        ("event_3", _scene(371)),
    ):
        _save_jpeg(
            root / event_id / "ORIGINALS" / "IMG_0001.jpg",
            original,
        )
        _save_jpeg(
            root / event_id / "EDITS" / "IMG_0001.jpg",
            np.clip(
                original.astype(np.float32) * 1.03 + 4.0,
                0,
                255,
            ).astype(np.uint8),
        )

    with pytest.raises(
        ValueError,
        match="divide one source group",
    ):
        _intake(
            root=root,
            output=tmp_path / "explicit-group-intake",
            photographer_id="fixture-photographer",
            aspect_tolerance=0.01,
            validation_events=["event_1"],
            test_events=["event_2"],
            rebuild_split_lock=True,
        )


def test_real_jpeg_intake_freezes_snapshot_and_detects_mutation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "dataset"
    output = tmp_path / "intake-output"

    for event_index in range(3):
        originals = root / f"event_{event_index + 1}" / "ORIGINALS"
        edits = root / f"event_{event_index + 1}" / "EDITS"

        original = _scene(100 + event_index)
        edited = np.clip(
            original.astype(np.float32) * (1.02 + event_index * 0.01) + 4.0,
            0,
            255,
        ).astype(np.uint8)

        _save_jpeg(originals / "IMG_0001.jpg", original)
        _save_jpeg(edits / "IMG_0001.jpg", edited)

    payload = _intake(
        root=root,
        output=output,
        photographer_id="fixture-photographer",
        aspect_tolerance=0.01,
        validation_events=[],
        test_events=[],
        rebuild_split_lock=False,
    )

    assert payload["working_color_space"] == WORKING_COLOR_SPACE
    assert payload["readiness"]["dataset_snapshot_frozen"] is True
    assert payload["readiness"]["color_contract_recorded"] is True
    assert payload["readiness"]["whole_event_train_validation_test_ready"] is True
    assert payload["totals"]["usable_recipe_pairs"] == 3
    assert payload["totals"]["geometry_excluded_pairs"] == 0
    assert payload["totals"]["color_excluded_pairs"] == 0

    for pair in payload["pairs"]:
        assert pair["geometry_action"] == "same_dimensions"
        assert pair["geometry_inliers"] >= 8
        assert pair["original_color_action"] == "assume_srgb_no_icc"
        assert pair["edited_color_action"] == "assume_srgb_no_icc"
        assert pair["working_color_space"] == WORKING_COLOR_SPACE

    snapshot_path = Path(payload["dataset_snapshot_path"])
    load_and_validate_dataset_snapshot(
        snapshot_path,
        expected_snapshot_id=payload["dataset_snapshot_id"],
    )

    changed = root / "event_1" / "ORIGINALS" / "IMG_0001.jpg"
    changed.write_bytes(changed.read_bytes() + b"changed-after-intake")

    with pytest.raises(
        DatasetSnapshotChangedError,
        match="source_changed_size",
    ):
        load_and_validate_dataset_snapshot(
            snapshot_path,
            expected_snapshot_id=payload["dataset_snapshot_id"],
        )

    # An intentional new Intake after source mutation creates a new immutable
    # dataset snapshot identity instead of silently continuing the old dataset.
    payload_v2 = _intake(
        root=root,
        output=tmp_path / "intake-output-v2",
        photographer_id="fixture-photographer",
        aspect_tolerance=0.01,
        validation_events=[],
        test_events=[],
        rebuild_split_lock=False,
    )
    assert payload_v2["dataset_snapshot_id"] != payload["dataset_snapshot_id"]
