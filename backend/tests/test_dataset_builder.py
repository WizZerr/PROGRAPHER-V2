from pathlib import Path

from app.datasets.builder import build_dataset_preview


def write_xmp(path: Path, exposure: str = "0.25") -> None:
    path.write_text(
        f"""<?xml version="1.0"?>
        <x:xmpmeta xmlns:x="adobe:ns:meta/"
          xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
          xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
          <rdf:RDF>
            <rdf:Description
              crs:Exposure2012="{exposure}"
              crs:Temperature="5200"
              crs:Tint="8"
              crs:Blacks2012="-12"
              crs:ProcessVersion="11.0"
              crs:CameraProfile="Adobe Color" />
          </rdf:RDF>
        </x:xmpmeta>
        """,
        encoding="utf-8",
    )


def test_pairs_raw_to_same_relative_xmp_but_does_not_claim_final_edit(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "RAW"
    edits_root = tmp_path / "EDITS"
    raw_root.mkdir()
    edits_root.mkdir()

    (raw_root / "IMG_0001.CR3").write_bytes(b"RAW-DATA" * 1000)
    write_xmp(edits_root / "IMG_0001.xmp")

    preview = build_dataset_preview(
        raw_root=raw_root,
        edits_root=edits_root,
        event_id="wedding-001",
    )

    assert preview.raw_files == 1
    assert preview.xmp_files == 1
    assert preview.matched_pairs == 1
    assert preview.verified_training_pairs == 0

    candidate = preview.candidates[0]
    assert candidate.pair_status == "matched"
    assert candidate.pairing_method == "relative_path_stem"
    assert candidate.final_edit_verified is False
    assert candidate.usable_for_training is False
    assert candidate.target_recipe is not None
    assert candidate.target_recipe.temperature == 5200


def test_duplicate_xmp_names_are_ambiguous_not_silently_paired(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "RAW"
    edits_root = tmp_path / "EDITS"
    raw_root.mkdir()
    (edits_root / "A").mkdir(parents=True)
    (edits_root / "B").mkdir(parents=True)

    (raw_root / "IMG_9999.NEF").write_bytes(b"RAW" * 1000)
    write_xmp(edits_root / "A" / "IMG_9999.xmp")
    write_xmp(edits_root / "B" / "IMG_9999.xmp")

    preview = build_dataset_preview(
        raw_root=raw_root,
        edits_root=edits_root,
        event_id="event-ambiguous",
    )

    assert preview.matched_pairs == 0
    assert preview.ambiguous_raw == 1
    assert preview.candidates[0].usable_for_training is False
