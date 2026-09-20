from app.domain.recipes import ProcessFamily
from app.services.recipe_service import recipe_to_xmp_attributes


def test_modern_blacks_maps_to_blacks2012() -> None:
    clean, attrs = recipe_to_xmp_attributes(
        {"blacks": -40},
        ProcessFamily.MODERN,
    )

    assert clean["blacks"] == -40.0
    assert attrs["Blacks2012"] == "-40"
    assert "Shadows" not in attrs


def test_legacy_blacks_maps_to_legacy_shadows_tag() -> None:
    clean, attrs = recipe_to_xmp_attributes(
        {"blacks": 5},
        ProcessFamily.LEGACY,
    )

    assert clean["blacks"] == 5.0
    assert attrs["Shadows"] == "5"
    assert "Blacks2012" not in attrs


def test_modern_exposure_plus_five_is_not_cut_to_three() -> None:
    clean, attrs = recipe_to_xmp_attributes(
        {"exposure": 5.0},
        ProcessFamily.MODERN,
    )

    assert clean["exposure"] == 5.0
    assert attrs["Exposure2012"] == "+5.00"


def test_legacy_controls_keep_their_own_xmp_fields() -> None:
    _, attrs = recipe_to_xmp_attributes(
        {
            "recovery": 25,
            "fill_light": 10,
            "brightness": 50,
        },
        ProcessFamily.LEGACY,
    )

    assert attrs["HighlightRecovery"] == "25"
    assert attrs["FillLight"] == "10"
    assert attrs["Brightness"] == "+50"
