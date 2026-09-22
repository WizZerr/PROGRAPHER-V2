from pathlib import Path

import pytest

from app.brain_v2.encoder_comparison.bundle_builder import (
    _camera_info,
    _raw_wb,
)
from app.brain_v2.encoder_comparison.manifest_adapter import (
    ManifestSample,
)


def sample(
    *,
    camera=None,
    exif=None,
    raw_info=None,
):
    return ManifestSample(
        sample_id="a",
        source_path="a.CR3",
        event_group="event-a",
        split="train",
        exposure_ev=0.0,
        temperature_k=5000.0,
        tint=0.0,
        camera=camera or {},
        exif=exif or {},
        raw_info=raw_info or {},
        capture_time=None,
    )


def test_camera_identity_is_taken_only_from_manifest_fields() -> None:
    info = _camera_info(
        sample(
            camera={
                "make": "Canon",
                "model": "EOS R6",
            }
        )
    )

    assert info.make == "Canon"
    assert info.model == "EOS R6"


def test_camera_model_is_not_guessed_from_filename() -> None:
    info = _camera_info(sample())

    assert info.make is None
    assert info.model is None


def test_raw_wb_accepts_manifest_raw_info() -> None:
    wb = _raw_wb(
        sample(
            raw_info={
                "raw_wb": [2.0, 1.0, 1.5, 1.0],
            }
        )
    )

    assert wb == (2.0, 1.0, 1.5, 1.0)
