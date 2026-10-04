from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageCms
import pytest

from app.datasets.jpeg_integrity import (
    DatasetSnapshotChangedError,
    JpegIntegrityError,
    WORKING_COLOR_SPACE,
    analyze_pair_geometry,
    load_and_validate_dataset_snapshot,
    read_jpeg_working_rgb,
)
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
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(rgb, mode="RGB")

    kwargs: dict = {"format": "JPEG", "quality": 98}
    if orientation is not None:
        exif = image.getexif()
        exif[274] = orientation
        kwargs["exif"] = exif

    if embed_srgb_icc:
        profile = ImageCms.ImageCmsProfile(
            ImageCms.createProfile("sRGB")
        )
        kwargs["icc_profile"] = profile.tobytes()

    image.save(path, **kwargs)


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
