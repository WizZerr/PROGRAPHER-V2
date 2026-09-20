from pathlib import Path

from app.evaluation.lightroom_reference_exercise import (
    ObservedLightroomRecipe,
    create_exercise,
    process_version_ui_label,
    verify_exercise,
)


EXPECTED = ObservedLightroomRecipe(
    exposure=0.35,
    temperature=5650,
    tint=-7,
    blacks=-40.0,
    process_version="Version 5",
    camera_profile="Adobe Standard",
)


def test_process_version_internal_to_lightroom_ui_mapping() -> None:
    assert process_version_ui_label("11.0") == "Version 5"
    assert process_version_ui_label("15.4") == "Version 6 (Current)"


def test_prepare_uses_copy_and_leaves_original_untouched(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "source.CR3"
    original = b"RAW-SOURCE" * 1000
    raw.write_bytes(original)

    workspace = create_exercise(
        raw_path=raw,
        workspace_root=tmp_path / "work",
    )

    fixture_raw = workspace / "fixture" / raw.name
    fixture_xmp = fixture_raw.with_suffix(".xmp")

    assert raw.read_bytes() == original
    assert fixture_raw.exists()
    assert fixture_raw.read_bytes() == original
    assert fixture_xmp.exists()
    assert not raw.with_suffix(".xmp").exists()


def test_verify_passes_with_exact_lightroom_observation_and_render(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "source.NEF"
    raw.write_bytes(b"RAW" * 1000)

    workspace = create_exercise(
        raw_path=raw,
        workspace_root=tmp_path / "work",
    )

    render = workspace / "render" / "lightroom-reference.jpg"
    render.write_bytes(b"REFERENCE")

    result = verify_exercise(
        workspace=workspace,
        observed=EXPECTED,
    )

    assert result.status == "PASS"
    assert result.source_unchanged is True
    assert result.fixture_raw_unchanged is True
    assert result.recipe_matches is True
    assert result.render_exists is True


def test_verify_fails_on_recipe_mismatch(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "source.ARW"
    raw.write_bytes(b"RAW" * 1000)

    workspace = create_exercise(
        raw_path=raw,
        workspace_root=tmp_path / "work",
    )

    render = workspace / "render" / "lightroom-reference.jpg"
    render.write_bytes(b"REFERENCE")

    result = verify_exercise(
        workspace=workspace,
        observed=ObservedLightroomRecipe(
            exposure=0.10,
            temperature=5650,
            tint=-7,
            blacks=-40.0,
            process_version="Version 5",
            camera_profile="Adobe Standard",
        ),
    )

    assert result.status == "FAIL"
    assert result.recipe_matches is False
    assert "exposure" in result.mismatches


def test_verify_detects_original_source_change(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "source.RAF"
    raw.write_bytes(b"RAW" * 1000)

    workspace = create_exercise(
        raw_path=raw,
        workspace_root=tmp_path / "work",
    )

    (workspace / "render" / "reference.jpg").write_bytes(b"REFERENCE")
    raw.write_bytes(b"CHANGED")

    result = verify_exercise(
        workspace=workspace,
        observed=EXPECTED,
    )

    assert result.status == "FAIL"
    assert result.source_unchanged is False
