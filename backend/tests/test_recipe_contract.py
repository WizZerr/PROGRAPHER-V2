import pytest

from app.domain.recipes import (
    ProcessFamily,
    RecipeValidationError,
    validate_recipe,
)


def test_modern_blacks_negative_40_is_preserved() -> None:
    result = validate_recipe(
        {"blacks": -40},
        ProcessFamily.MODERN,
    )

    assert result["blacks"] == -40.0


def test_legacy_blacks_keeps_legacy_range() -> None:
    result = validate_recipe(
        {"blacks": 5},
        ProcessFamily.LEGACY,
    )

    assert result["blacks"] == 5.0


def test_legacy_blacks_negative_value_is_rejected_not_clipped() -> None:
    with pytest.raises(RecipeValidationError):
        validate_recipe(
            {"blacks": -40},
            ProcessFamily.LEGACY,
        )


@pytest.mark.parametrize("value", [-5.0, 5.0])
def test_exposure_contract_edges_are_preserved(value: float) -> None:
    result = validate_recipe(
        {"exposure": value},
        ProcessFamily.MODERN,
    )

    assert result["exposure"] == value


@pytest.mark.parametrize("value", [-5.01, 5.01])
def test_exposure_outside_contract_is_rejected_not_silently_clipped(
    value: float,
) -> None:
    with pytest.raises(RecipeValidationError):
        validate_recipe(
            {"exposure": value},
            ProcessFamily.MODERN,
        )
