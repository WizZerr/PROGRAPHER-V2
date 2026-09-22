from __future__ import annotations

from pathlib import Path

from app.brain_v2.training.dataset_manifest import (
    build_dataset_manifest_from_readiness,
)
from tools.phase12_dataset_readiness import build_report


XMP = """<?xpacket begin="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description
      xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
      crs:ProcessVersion="11.0"
      crs:WhiteBalance="Custom"
      crs:Temperature="5650"
      crs:Tint="-7"
      crs:Exposure2012="+0.35"
      crs:CameraProfile="Adobe Standard"
      crs:ToneCurveName2012="Medium Contrast"/>
  </rdf:RDF>
</x:xmpmeta>
"""


def _pair(event: Path, stem: str, raw_bytes: bytes) -> None:
    raw = event / f"{stem}.cr3"
    raw.write_bytes(raw_bytes)
    raw.with_suffix(".cr3.xmp").write_text(
        XMP,
        encoding="utf-8",
    )


def _report(root: Path):
    return build_report(
        root=root,
        preset_identity="none",
        tone_curve_identity=None,
        hash_raws=True,
    )


def test_manifest_contains_stable_content_identity(tmp_path: Path) -> None:
    e1 = tmp_path / "event-a"
    e2 = tmp_path / "event-b"
    e1.mkdir()
    e2.mkdir()
    _pair(e1, "a", b"raw-a")
    _pair(e2, "b", b"raw-b")

    first = build_dataset_manifest_from_readiness(
        _report(tmp_path)
    )
    second = build_dataset_manifest_from_readiness(
        _report(tmp_path)
    )

    assert first.dataset_id == second.dataset_id
    assert [x.sample_id for x in first.samples] == [
        x.sample_id for x in second.samples
    ]


def test_manifest_preserves_event_grouping(tmp_path: Path) -> None:
    e1 = tmp_path / "event-a"
    e2 = tmp_path / "event-b"
    e1.mkdir()
    e2.mkdir()
    _pair(e1, "a", b"a")
    _pair(e2, "b", b"b")

    manifest = build_dataset_manifest_from_readiness(
        _report(tmp_path)
    )

    assert manifest.usable_event_ids == (
        "event-a",
        "event-b",
    )
    assert manifest.event_safe_split_ready is True


def test_manifest_contains_raw_and_xmp_hashes(tmp_path: Path) -> None:
    event = tmp_path / "event-a"
    event.mkdir()
    _pair(event, "a", b"abc")

    manifest = build_dataset_manifest_from_readiness(
        _report(tmp_path)
    )
    sample = manifest.samples[0]

    assert len(sample.raw_sha256) == 64
    assert len(sample.xmp_sha256 or "") == 64
    assert sample.raw_relpath == "event-a/a.cr3"
    assert sample.xmp_relpath == "event-a/a.cr3.xmp"


def test_target_and_rendering_context_are_frozen_into_manifest(
    tmp_path: Path,
) -> None:
    event = tmp_path / "event-a"
    event.mkdir()
    _pair(event, "a", b"a")

    manifest = build_dataset_manifest_from_readiness(
        _report(tmp_path)
    )
    sample = manifest.samples[0]

    assert sample.targets == {
        "exposure_stops": 0.35,
        "temperature_k": 5650,
        "tint": -7,
    }
    assert sample.rendering_context is not None
    assert (
        sample.rendering_context["camera_profile"]
        == "Adobe Standard"
    )


def test_missing_xmp_stays_explicit_in_manifest(tmp_path: Path) -> None:
    event = tmp_path / "event-a"
    event.mkdir()
    raw = event / "a.cr3"
    raw.write_bytes(b"a")

    manifest = build_dataset_manifest_from_readiness(
        _report(tmp_path)
    )
    sample = manifest.samples[0]

    assert sample.xmp_path is None
    assert sample.xmp_sha256 is None
    assert sample.pair_status == "missing_xmp"
    assert sample.ready_for_three_target_training is False
