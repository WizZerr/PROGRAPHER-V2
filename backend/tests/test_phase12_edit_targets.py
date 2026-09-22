from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.brain_v2.models.edit_targets import (
    LightroomEditTargets,
    LightroomRenderingContext,
    Phase12TargetSample,
    WhiteBalanceTargetMode,
    build_white_balance_learning_target,
)


def _context(**overrides):
    values = {
        "source_kind": "camera_raw",
        "process_version": "11.0",
        "camera_profile": "Adobe Standard",
        "tone_curve": "known-default",
        "preset_identity": "none",
        "white_balance_mode": "Custom",
        "as_shot_temperature_k": 5200,
        "as_shot_tint": 4,
        "wb_mapping_reliable": True,
    }
    values.update(overrides)
    return LightroomRenderingContext(**values)


def test_three_targets_complete_and_training_ready() -> None:
    targets = LightroomEditTargets(
        exposure_stops=0.35,
        temperature_k=5650,
        tint=-7,
    )
    sample = Phase12TargetSample(targets=targets, rendering_context=_context())
    assert targets.missing_fields == ()
    assert sample.ready_for_three_target_training is True


def test_missing_targets_are_explicit() -> None:
    targets = LightroomEditTargets(exposure_stops=0.2)
    assert targets.missing_fields == ("temperature_k", "tint")
    assert targets.ready_for_three_target_training is False


@pytest.mark.parametrize("value", [-5.01, 5.01, float("inf"), float("nan")])
def test_exposure_rejects_out_of_contract_values(value: float) -> None:
    with pytest.raises(ValidationError):
        LightroomEditTargets(exposure_stops=value)


@pytest.mark.parametrize("value", [1999, 50001])
def test_temperature_rejects_out_of_raw_contract_values(value: int) -> None:
    with pytest.raises(ValidationError):
        LightroomEditTargets(temperature_k=value)


@pytest.mark.parametrize("value", [-151, 151])
def test_tint_rejects_out_of_contract_values(value: int) -> None:
    with pytest.raises(ValidationError):
        LightroomEditTargets(tint=value)


def test_rendering_context_requires_explicit_profile_curve_and_preset() -> None:
    with pytest.raises(ValidationError):
        _context(camera_profile="   ")


def test_absolute_kelvin_does_not_treat_5000_as_zero() -> None:
    targets = LightroomEditTargets(exposure_stops=0.0, temperature_k=5000, tint=0)
    wb = build_white_balance_learning_target(
        targets=targets,
        rendering_context=_context(),
        mode=WhiteBalanceTargetMode.ABSOLUTE_KELVIN,
    )
    assert wb.temperature == 5000
    assert wb.tint == 0


def test_delta_from_as_shot_requires_reliable_mapping() -> None:
    targets = LightroomEditTargets(exposure_stops=0.0, temperature_k=5650, tint=-7)
    with pytest.raises(ValueError, match="wb_mapping_reliable"):
        build_white_balance_learning_target(
            targets=targets,
            rendering_context=_context(
                wb_mapping_reliable=False,
                as_shot_temperature_k=None,
                as_shot_tint=None,
            ),
            mode=WhiteBalanceTargetMode.DELTA_FROM_AS_SHOT,
        )


def test_delta_from_as_shot_is_computed_only_when_mapping_is_reliable() -> None:
    targets = LightroomEditTargets(exposure_stops=0.0, temperature_k=5650, tint=-7)
    wb = build_white_balance_learning_target(
        targets=targets,
        rendering_context=_context(
            as_shot_temperature_k=5200,
            as_shot_tint=4,
            wb_mapping_reliable=True,
        ),
        mode=WhiteBalanceTargetMode.DELTA_FROM_AS_SHOT,
    )
    assert wb.temperature == 450
    assert wb.tint == -11
