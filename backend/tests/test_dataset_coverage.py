from pathlib import Path

import app.datasets.builder as builder_module
from app.datasets.builder import build_dataset_preview
from app.datasets.contracts import DatasetRights, SourceMetadata
from app.datasets.coverage import summarize_coverage
from app.datasets.review import apply_review_decisions


def _xmp(path: Path) -> None:
    path.write_text(
        """<x:xmpmeta xmlns:x="adobe:ns:meta/"
             xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
             xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
             <rdf:RDF><rdf:Description
               crs:Exposure2012="0"
               crs:Temperature="5000"
               crs:Tint="0" /></rdf:RDF>
           </x:xmpmeta>""",
        encoding="utf-8",
    )


def test_coverage_requires_more_than_count_alone(
    tmp_path: Path,
    monkeypatch,
) -> None:
    raw = tmp_path / "raw"
    edits = tmp_path / "edits"
    raw.mkdir()
    edits.mkdir()

    (raw / "A.CR3").write_bytes(b"RAW" * 1000)
    _xmp(edits / "A.xmp")

    monkeypatch.setattr(
        builder_module,
        "extract_source_metadata",
        lambda _: SourceMetadata(
            camera_model="Canon EOS R6",
            captured_at="2026:09:20 10:00:00",
        ),
    )

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

    coverage = summarize_coverage(
        [reviewed],
        rights=DatasetRights(
            permission_basis="photographer_owned",
            allow_personal_training=True,
        ),
    )

    assert coverage.verified_training_pairs == 1
    assert coverage.usable_personal_training_pairs == 1
    assert coverage.readiness_state == "needs_more_data"
    assert any("אירוע אחד" in reason for reason in coverage.readiness_reasons)
    assert coverage.lighting_coverage_status == "not_measured"
