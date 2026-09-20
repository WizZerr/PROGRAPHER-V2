from pathlib import Path

import app.datasets.builder as builder_module
from app.datasets.builder import build_dataset_preview
from app.datasets.contracts import SourceMetadata


def test_builder_records_camera_time_photographer_and_source_group(
    tmp_path: Path,
    monkeypatch,
) -> None:
    raw_root = tmp_path / "raw"
    edits_root = tmp_path / "edits"
    sequence = raw_root / "ceremony"
    sequence.mkdir(parents=True)
    (edits_root / "ceremony").mkdir(parents=True)

    raw = sequence / "IMG_1000.ARW"
    raw.write_bytes(b"RAW" * 1000)

    (edits_root / "ceremony" / "IMG_1000.xmp").write_text(
        """<x:xmpmeta xmlns:x="adobe:ns:meta/"
             xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
             xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
             <rdf:RDF><rdf:Description
               crs:Exposure2012="0"
               crs:Temperature="5200"
               crs:Tint="5" /></rdf:RDF>
           </x:xmpmeta>""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        builder_module,
        "extract_source_metadata",
        lambda _: SourceMetadata(
            camera_make="Sony",
            camera_model="ILCE-7M4",
            captured_at="2026:09:20 18:00:00",
            iso=800,
            shutter_seconds=0.01,
            aperture=2.8,
            focal_length_mm=35.0,
            raw_wb=(2.0, 1.0, 1.5, 1.0),
            raw_wb_source="test",
        ),
    )

    preview = build_dataset_preview(
        raw_root=raw_root,
        edits_root=edits_root,
        event_id="event-1",
        photographer_id="photographer-local",
        lightroom_version="15.0",
        style_label="Natural Wedding",
    )

    candidate = preview.candidates[0]

    assert candidate.source_metadata is not None
    assert candidate.source_metadata.camera_model == "ILCE-7M4"
    assert candidate.source_metadata.raw_wb == (2.0, 1.0, 1.5, 1.0)
    assert candidate.sequence_id == "ceremony"
    assert candidate.photographer_id == "photographer-local"
    assert candidate.lightroom_version == "15.0"
    assert candidate.style_label == "Natural Wedding"
