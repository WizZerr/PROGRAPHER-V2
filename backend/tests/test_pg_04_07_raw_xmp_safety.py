from __future__ import annotations

from pathlib import Path

import pytest

from app.datasets.contracts import TargetRecipe
from app.testing import sidecar
from app.testing.sidecar import (
    EXPORT_MARKER,
    SidecarExportError,
    write_testing_sidecar,
)


def _recipe(exposure: float) -> TargetRecipe:
    return TargetRecipe(
        exposure=exposure,
        temperature=5200,
        tint=4,
        blacks=None,
        process_version="15.4",
        camera_profile="Adobe Color",
    )


def test_foreign_xmp_is_never_replaced(tmp_path: Path) -> None:
    raw = tmp_path / "IMG_0407.ARW"
    raw.write_bytes(b"raw-source" * 200)
    destination = tmp_path / "out" / "event" / "IMG_0407.xmp"
    destination.parent.mkdir(parents=True)
    foreign = b"<?xml version='1.0'?><foreign-xmp/>"
    destination.write_bytes(foreign)

    with pytest.raises(SidecarExportError, match="לא הוחלף"):
        write_testing_sidecar(
            raw_path=raw,
            relative_path="IMG_0407.ARW",
            recipe=_recipe(0.2),
            output_dir=tmp_path / "out",
            export_namespace="event",
        )

    assert destination.read_bytes() == foreign


def test_raw_change_before_promotion_keeps_previous_prographer_xmp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    raw = tmp_path / "IMG_0407.ARW"
    raw.write_bytes(b"raw-source" * 200)
    output = tmp_path / "out"

    destination = write_testing_sidecar(
        raw_path=raw,
        relative_path="IMG_0407.ARW",
        recipe=_recipe(0.2),
        output_dir=output,
        export_namespace="event",
    )
    previous = destination.read_bytes()
    assert EXPORT_MARKER.encode() in previous

    hashes = iter(("source-a", "source-b"))
    monkeypatch.setattr(sidecar, "_sha256", lambda path: next(hashes))

    with pytest.raises(SidecarExportError, match="השתנה"):
        write_testing_sidecar(
            raw_path=raw,
            relative_path="IMG_0407.ARW",
            recipe=_recipe(0.6),
            output_dir=output,
            export_namespace="event",
        )

    assert destination.read_bytes() == previous
    assert not destination.with_suffix(".xmp.tmp").exists()


def test_raw_change_after_promotion_rolls_back_previous_xmp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    raw = tmp_path / "IMG_0407.ARW"
    raw.write_bytes(b"raw-source" * 200)
    output = tmp_path / "out"

    destination = write_testing_sidecar(
        raw_path=raw,
        relative_path="IMG_0407.ARW",
        recipe=_recipe(0.2),
        output_dir=output,
        export_namespace="event",
    )
    previous = destination.read_bytes()

    hashes = iter(("source-a", "source-a", "source-b"))
    monkeypatch.setattr(sidecar, "_sha256", lambda path: next(hashes))

    with pytest.raises(SidecarExportError, match="שוחזר"):
        write_testing_sidecar(
            raw_path=raw,
            relative_path="IMG_0407.ARW",
            recipe=_recipe(0.8),
            output_dir=output,
            export_namespace="event",
        )

    assert destination.read_bytes() == previous
    assert not destination.with_suffix(".xmp.tmp").exists()
    assert not destination.with_suffix(".xmp.rollback.tmp").exists()


def test_first_export_is_removed_if_raw_changes_after_promotion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    raw = tmp_path / "IMG_0407.ARW"
    raw.write_bytes(b"raw-source" * 200)
    output = tmp_path / "out"

    hashes = iter(("source-a", "source-a", "source-b"))
    monkeypatch.setattr(sidecar, "_sha256", lambda path: next(hashes))

    with pytest.raises(SidecarExportError, match="שוחזר"):
        write_testing_sidecar(
            raw_path=raw,
            relative_path="IMG_0407.ARW",
            recipe=_recipe(0.4),
            output_dir=output,
            export_namespace="event",
        )

    destination = output / "event" / "IMG_0407.xmp"
    assert not destination.exists()
    assert not destination.with_suffix(".xmp.tmp").exists()
