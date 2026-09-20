from pathlib import Path

from app.datasets.contracts import TargetRecipe
from app.lightroom_bridge.xmp_roundtrip import run_reference_roundtrip


def test_known_recipe_roundtrip_preserves_values_and_raw(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "IMG_0001.CR3"
    raw.write_bytes(b"RAW-DATA" * 1000)
    output = tmp_path / "reference-xmp"

    recipe = TargetRecipe(
        exposure=0.35,
        temperature=5650,
        tint=-7,
        blacks=-40.0,
        process_version="11.0",
        camera_profile="Adobe Color",
    )

    result = run_reference_roundtrip(
        raw_path=raw,
        recipe=recipe,
        output_dir=output,
    )

    assert result.source_unchanged is True
    assert result.recipe_matches is True
    assert result.mismatches == ()
    assert Path(result.written_xmp_path).exists()
    assert Path(result.written_xmp_path).parent == output.resolve()
    assert not (tmp_path / "IMG_0001.xmp").exists()
