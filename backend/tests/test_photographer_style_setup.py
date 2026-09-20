from pathlib import Path

from app.photographer.presets import validate_preset
from app.photographer.setup_store import PhotographerSetupStore
from app.services.photographer_setup_service import save_style_preferences


def test_style_preferences_persist_without_claiming_ready(
    tmp_path: Path,
) -> None:
    store = PhotographerSetupStore(tmp_path / "state.sqlite3")
    store.save_no_source()

    overview = save_style_preferences(
        style_name="Wedding Natural",
        preset_path=None,
        color_profile_mode="from_source",
        camera_profile=None,
        store=store,
    )

    assert overview.setup.style_name == "Wedding Natural"
    assert overview.setup.status == "needs_more_data"
    assert overview.readiness_reasons


def test_explicit_camera_profile_requires_name(tmp_path: Path) -> None:
    store = PhotographerSetupStore(tmp_path / "state.sqlite3")

    try:
        save_style_preferences(
            style_name=None,
            preset_path=None,
            color_profile_mode="explicit",
            camera_profile=None,
            store=store,
        )
    except ValueError:
        return

    raise AssertionError("explicit profile mode must require a name")


def test_manual_xmp_preset_is_validated(tmp_path: Path) -> None:
    preset = tmp_path / "My Wedding Preset.xmp"
    preset.write_text("<x:xmpmeta/>", encoding="utf-8")

    result = validate_preset(preset)

    assert result.path == str(preset.resolve())
    assert result.name == "My Wedding Preset"
