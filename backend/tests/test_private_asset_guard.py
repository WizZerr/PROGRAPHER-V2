from tools.check_private_assets import is_private_asset


def test_blocks_photographer_catalog_preview_and_camera_data():
    for path in (
        "private/Lightroom.lrcat",
        "private/Lightroom.lrcat-wal",
        "private/Lightroom Smart Previews.lrdata/1.dat",
        "private/Lightroom.lrcat-data/1.dat",
        "albums/example.CR3",
        "albums/example.NEF",
        "meta/photo.xmp",
        "analysis/PRIVATE_manifest.json",
        "private-research/image.bin",
    ):
        assert is_private_asset(path), path


def test_keeps_synthetic_code_and_public_ui_assets():
    for path in (
        "backend/tests/test_smart_preview_intake.py",
        "frontend/public/training-raw-hero.png",
        "docs/MASTER_PLAN_SOURCE_OF_TRUTH.md",
        "backend/app/photographer/lightroom.py",
        ".github/workflows/intake-privacy-guard.yml",
    ):
        assert not is_private_asset(path), path
