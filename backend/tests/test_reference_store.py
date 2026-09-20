import json
from pathlib import Path

from app.datasets.contracts import SourceIdentity, TargetRecipe
from app.reference.store import REFERENCE_SCHEMA, register_lightroom_render


def test_lightroom_reference_manifest_records_render_truth(
    tmp_path: Path,
) -> None:
    render = tmp_path / "reference.jpg"
    render.write_bytes(b"fake-lightroom-render")

    source = SourceIdentity(
        absolute_path=str(tmp_path / "RAW.CR3"),
        relative_path="RAW.CR3",
        filename="RAW.CR3",
        extension=".CR3",
        size_bytes=123,
        modified_ns=456,
        fingerprint="source-fingerprint",
    )

    recipe = TargetRecipe(
        exposure=0.1,
        temperature=5100,
        tint=3,
        blacks=-40.0,
        process_version="11.0",
        camera_profile="Adobe Color",
    )

    case, manifest_path = register_lightroom_render(
        source=source,
        recipe=recipe,
        render_path=render,
        color_space="sRGB IEC61966-2.1",
        file_format="JPEG",
        process_family="modern",
        lightroom_version="15.0",
        output_dir=tmp_path / "manifests",
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["schema"] == REFERENCE_SCHEMA
    assert payload["render"]["render_kind"] == "lightroom_export"
    assert payload["render"]["color_space"] == "sRGB IEC61966-2.1"
    assert payload["source"]["fingerprint"] == "source-fingerprint"
    assert payload["recipe"]["blacks"] == -40.0
    assert case.status == "reference_registered"
