from __future__ import annotations

from pathlib import Path

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


def _raw(event: Path, name: str, payload: bytes = b"raw") -> Path:
    path = event / name
    path.write_bytes(payload)
    return path


def _xmp_for(raw: Path, text: str = XMP) -> Path:
    path = raw.with_suffix(raw.suffix + ".xmp")
    path.write_text(text, encoding="utf-8")
    return path


def test_two_events_with_complete_pairs_are_split_ready(tmp_path: Path) -> None:
    e1 = tmp_path / "event-a"
    e2 = tmp_path / "event-b"
    e1.mkdir()
    e2.mkdir()

    r1 = _raw(e1, "a.cr3", b"a")
    r2 = _raw(e2, "b.dng", b"b")
    _xmp_for(r1)
    _xmp_for(r2)

    report = build_report(
        root=tmp_path,
        preset_identity="none",
        tone_curve_identity=None,
        hash_raws=True,
    )

    assert report["summary"]["event_count"] == 2
    assert report["summary"]["training_ready_count"] == 2
    assert report["summary"]["event_safe_split_ready"] is True
    assert report["readiness_gate"]["can_start_three_target_training"] is True


def test_one_event_is_not_event_safe_split_ready(tmp_path: Path) -> None:
    event = tmp_path / "event-a"
    event.mkdir()
    raw = _raw(event, "a.cr3")
    _xmp_for(raw)

    report = build_report(
        root=tmp_path,
        preset_identity="none",
        tone_curve_identity=None,
        hash_raws=True,
    )

    assert report["summary"]["usable_event_count"] == 1
    assert report["summary"]["event_safe_split_ready"] is False
    assert report["readiness_gate"]["can_start_three_target_training"] is False


def test_missing_xmp_is_counted_not_guessed(tmp_path: Path) -> None:
    event = tmp_path / "event-a"
    event.mkdir()
    _raw(event, "a.cr3")

    report = build_report(
        root=tmp_path,
        preset_identity="none",
        tone_curve_identity=None,
        hash_raws=True,
    )

    assert report["summary"]["missing_xmp_count"] == 1
    assert report["summary"]["training_ready_count"] == 0


def test_duplicate_raw_hash_is_reported(tmp_path: Path) -> None:
    e1 = tmp_path / "event-a"
    e2 = tmp_path / "event-b"
    e1.mkdir()
    e2.mkdir()

    r1 = _raw(e1, "a.cr3", b"same")
    r2 = _raw(e2, "b.cr3", b"same")
    _xmp_for(r1)
    _xmp_for(r2)

    report = build_report(
        root=tmp_path,
        preset_identity="none",
        tone_curve_identity=None,
        hash_raws=True,
    )

    assert report["summary"]["duplicate_raw_group_count"] == 1
    assert report["duplicate_raw_groups"][0]["count"] == 2
    assert report["duplicate_raw_groups"][0]["event_ids"] == [
        "event-a",
        "event-b",
    ]


def test_incomplete_target_is_not_training_ready(tmp_path: Path) -> None:
    e1 = tmp_path / "event-a"
    e2 = tmp_path / "event-b"
    e1.mkdir()
    e2.mkdir()

    complete = _raw(e1, "a.cr3", b"a")
    incomplete = _raw(e2, "b.cr3", b"b")
    _xmp_for(complete)
    _xmp_for(
        incomplete,
        XMP.replace('      crs:Tint="-7"\n', ""),
    )

    report = build_report(
        root=tmp_path,
        preset_identity="none",
        tone_curve_identity=None,
        hash_raws=True,
    )

    assert report["summary"]["training_ready_count"] == 1
    assert report["summary"]["missing_targets_count"] == 1
    assert report["summary"]["usable_event_count"] == 1
    assert report["readiness_gate"]["can_start_three_target_training"] is False


def test_invalid_rendering_context_is_a_blocker(tmp_path: Path) -> None:
    e1 = tmp_path / "event-a"
    e2 = tmp_path / "event-b"
    e1.mkdir()
    e2.mkdir()

    r1 = _raw(e1, "a.cr3", b"a")
    r2 = _raw(e2, "b.cr3", b"b")
    _xmp_for(r1)
    _xmp_for(
        r2,
        XMP.replace('      crs:CameraProfile="Adobe Standard"\n', ""),
    )

    report = build_report(
        root=tmp_path,
        preset_identity="none",
        tone_curve_identity=None,
        hash_raws=True,
    )

    assert report["summary"]["invalid_or_error_count"] == 1
    assert report["readiness_gate"]["can_start_three_target_training"] is False
