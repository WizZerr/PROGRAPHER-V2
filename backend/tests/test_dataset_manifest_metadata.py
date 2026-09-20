from pathlib import Path

import app.datasets.builder as builder_module
from app.datasets.builder import build_dataset_preview
from app.datasets.contracts import DatasetRights, SourceMetadata
from app.datasets.manifest import write_manifest
from app.datasets.review import apply_review_decisions


def test_manifest_contains_metadata_rights_and_coverage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    raw = tmp_path / "raw"
    edits = tmp_path / "edits"
    manifests = tmp_path / "manifests"
    raw.mkdir()
    edits.mkdir()

    (raw / "IMG_1.NEF").write_bytes(b"RAW" * 1000)
    (edits / "IMG_1.xmp").write_text(
        """<x:xmpmeta xmlns:x="adobe:ns:meta/"
             xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
             xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
             <rdf:RDF><rdf:Description
               crs:Exposure2012="0.3"
               crs:Temperature="4900"
               crs:Tint="-2" /></rdf:RDF>
           </x:xmpmeta>""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        builder_module,
        "extract_source_metadata",
        lambda _: SourceMetadata(
            camera_make="Nikon",
            camera_model="NIKON Z 6_2",
            captured_at="2026:09:20 20:15:00",
            raw_wb=(1.9, 1.0, 1.4, 1.0),
            raw_wb_source="test",
        ),
    )

    preview = build_dataset_preview(
        raw_root=raw,
        edits_root=edits,
        event_id="event-1",
        photographer_id="local",
    )
    fingerprint = preview.candidates[0].source.fingerprint
    reviewed = apply_review_decisions(
        preview,
        {fingerprint: "verified_final"},
    )

    _, _, payload = write_manifest(
        [reviewed],
        output_dir=manifests,
        rights=DatasetRights(
            permission_basis="photographer_owned",
            allow_personal_training=True,
        ),
    )

    sample = payload["samples"][0]

    assert payload["version"] == 2
    assert payload["rights"]["allow_general_training"] is False
    assert payload["coverage"]["camera_models"]["NIKON Z 6_2"] == 1
    assert sample["source_metadata"]["camera_model"] == "NIKON Z 6_2"
    assert sample["rights"]["eligible_for_personal_training"] is True
    assert sample["rights"]["eligible_for_general_training"] is False
