from pathlib import Path

from app.datasets.builder import build_dataset_preview
from app.datasets.review import apply_review_decisions


def write_xmp(path: Path, *, local_adjustment: bool = False) -> None:
    extra = ' crs:HasMask="True"' if local_adjustment else ""

    path.write_text(
        f"""<x:xmpmeta xmlns:x="adobe:ns:meta/"
             xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
             xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
             <rdf:RDF><rdf:Description
               crs:Exposure2012="0"
               crs:Temperature="5000"
               crs:Tint="0"{extra} /></rdf:RDF>
           </x:xmpmeta>""",
        encoding="utf-8",
    )


def test_explicit_final_edit_review_makes_clean_pair_usable(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    edits = tmp_path / "edits"
    raw.mkdir()
    edits.mkdir()

    (raw / "A.CR3").write_bytes(b"RAW" * 1000)
    write_xmp(edits / "A.xmp")

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

    assert reviewed.verified_training_pairs == 1
    candidate = reviewed.candidates[0]
    assert candidate.final_edit_verified is True
    assert candidate.usable_for_training is True


def test_local_adjustments_remain_excluded_even_after_final_review(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    edits = tmp_path / "edits"
    raw.mkdir()
    edits.mkdir()

    (raw / "B.NEF").write_bytes(b"RAW" * 1000)
    write_xmp(edits / "B.xmp", local_adjustment=True)

    preview = build_dataset_preview(
        raw_root=raw,
        edits_root=edits,
        event_id="event-2",
    )

    fingerprint = preview.candidates[0].source.fingerprint

    reviewed = apply_review_decisions(
        preview,
        {fingerprint: "verified_final"},
    )

    candidate = reviewed.candidates[0]
    assert candidate.final_edit_verified is True
    assert candidate.usable_for_training is False
    assert "local_adjustments_out_of_initial_scope" in candidate.exclusion_reasons
    assert reviewed.verified_training_pairs == 0
