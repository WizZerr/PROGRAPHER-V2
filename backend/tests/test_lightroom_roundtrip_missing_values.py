from pathlib import Path

from app.datasets.contracts import TargetRecipe
from app.lightroom_bridge.xmp_roundtrip import run_reference_roundtrip


def test_roundtrip_preserves_missing_as_missing_and_zero_as_zero(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "A.NEF"
    raw.write_bytes(b"RAW" * 500)

    recipe = TargetRecipe(
        exposure=0.0,
        temperature=None,
        tint=0,
        blacks=None,
        process_version=None,
        camera_profile=None,
    )

    result = run_reference_roundtrip(
        raw_path=raw,
        recipe=recipe,
        output_dir=tmp_path / "xmp",
    )

    assert result.recipe_matches is True
    assert result.source_unchanged is True
