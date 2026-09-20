import json
from pathlib import Path

from app.datasets.builder import build_dataset_preview
from app.datasets.manifest import (
    DATASET_MANIFEST_SCHEMA,
    write_manifest,
)
from app.datasets.review import apply_review_decisions


def write_xmp(path: Path) -> None:
    path.write_text(
        """<x:xmpmeta xmlns:x="adobe:ns:meta/"
             xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
             xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
             <rdf:RDF><rdf:Description
               crs:Exposure2012="0.2"
               crs:Temperature="5100"
               crs:Tint="4"
               crs:ProcessVersion="11.0"
               crs:CameraProfile="Adobe Color" /></rdf:RDF>
           </x:xmpmeta>""",
        encoding="utf-8",
    )


def test_manifest_is_versioned_atomic_and_contains_provenance(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    edits = tmp_path / "edits"
    manifests = tmp_path / "manifests"
    raw.mkdir()
    edits.mkdir()

    (raw / "IMG_1.ARW").write_bytes(b"RAW" * 1000)
    write_xmp(edits / "IMG_1.xmp")

    preview = build_dataset_preview(
        raw_root=raw,
        edits_root=edits,
        event_id="event-1",
    )
    fingerprint = preview.candidates[0].source.fingerprint
    reviewed = apply_review_decisions(
        preview,
        {fingerprint: "verified_final"},
    )

    manifest_id, path, payload = write_manifest(
        [reviewed],
        output_dir=manifests,
    )

    assert manifest_id
    assert path.exists()
    assert not path.with_suffix(".json.tmp").exists()
    assert payload["schema"] == DATASET_MANIFEST_SCHEMA
    assert payload["split_scope"] == "event"
    assert payload["samples"][0]["usable_for_training"] is True
    assert payload["samples"][0]["provenance"]["edit_source_type"] == "lightroom_xmp"

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["manifest_id"] == manifest_id
