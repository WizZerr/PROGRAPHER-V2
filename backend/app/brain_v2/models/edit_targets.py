from __future__ import annotations

from enum import Enum
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EXPOSURE_MIN_STOPS = -5.0
EXPOSURE_MAX_STOPS = 5.0
TEMPERATURE_MIN_K = 2000
TEMPERATURE_MAX_K = 50000
TINT_MIN = -150
TINT_MAX = 150


class WhiteBalanceTargetMode(str, Enum):
    ABSOLUTE_KELVIN = "absolute_kelvin"
    DELTA_FROM_AS_SHOT = "delta_from_as_shot"


class LightroomEditTargets(BaseModel):
    model_config = ConfigDict(frozen=True)

    exposure_stops: float | None = Field(default=None)
    temperature_k: int | None = Field(default=None)
    tint: int | None = Field(default=None)

    @field_validator("exposure_stops")
    @classmethod
    def validate_exposure(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if not math.isfinite(value):
            raise ValueError("exposure_stops must be finite")
        if not EXPOSURE_MIN_STOPS <= value <= EXPOSURE_MAX_STOPS:
            raise ValueError(
                f"exposure_stops must be within [{EXPOSURE_MIN_STOPS}, {EXPOSURE_MAX_STOPS}]"
            )
        return float(value)

    @field_validator("temperature_k")
    @classmethod
    def validate_temperature(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if not TEMPERATURE_MIN_K <= value <= TEMPERATURE_MAX_K:
            raise ValueError(
                f"temperature_k must be within [{TEMPERATURE_MIN_K}, {TEMPERATURE_MAX_K}] for RAW"
            )
        return int(value)

    @field_validator("tint")
    @classmethod
    def validate_tint(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if not TINT_MIN <= value <= TINT_MAX:
            raise ValueError(f"tint must be within [{TINT_MIN}, {TINT_MAX}]")
        return int(value)

    @property
    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.exposure_stops is None:
            missing.append("exposure_stops")
        if self.temperature_k is None:
            missing.append("temperature_k")
        if self.tint is None:
            missing.append("tint")
        return tuple(missing)

    @property
    def ready_for_three_target_training(self) -> bool:
        return not self.missing_fields


class LightroomRenderingContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_kind: Literal["camera_raw", "dng_raw"]
    process_version: str
    camera_profile: str
    tone_curve: str
    preset_identity: str

    white_balance_mode: str | None = None
    as_shot_temperature_k: int | None = None
    as_shot_tint: int | None = None
    wb_mapping_reliable: bool = False

    @field_validator("process_version", "camera_profile", "tone_curve", "preset_identity")
    @classmethod
    def require_known_rendering_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("rendering context values must be explicit")
        return value

    @field_validator("as_shot_temperature_k")
    @classmethod
    def validate_as_shot_temperature(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if not TEMPERATURE_MIN_K <= value <= TEMPERATURE_MAX_K:
            raise ValueError(
                f"as_shot_temperature_k must be within [{TEMPERATURE_MIN_K}, {TEMPERATURE_MAX_K}]"
            )
        return int(value)

    @field_validator("as_shot_tint")
    @classmethod
    def validate_as_shot_tint(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if not TINT_MIN <= value <= TINT_MAX:
            raise ValueError(f"as_shot_tint must be within [{TINT_MIN}, {TINT_MAX}]")
        return int(value)

    @model_validator(mode="after")
    def reliable_wb_requires_as_shot_values(self) -> "LightroomRenderingContext":
        if self.wb_mapping_reliable and (
            self.as_shot_temperature_k is None or self.as_shot_tint is None
        ):
            raise ValueError(
                "wb_mapping_reliable=True requires both as_shot_temperature_k and as_shot_tint"
            )
        return self


class WhiteBalanceLearningTarget(BaseModel):
    model_config = ConfigDict(frozen=True)
    mode: WhiteBalanceTargetMode
    temperature: int
    tint: int


class Phase12TargetSample(BaseModel):
    model_config = ConfigDict(frozen=True)
    targets: LightroomEditTargets
    rendering_context: LightroomRenderingContext

    @property
    def ready_for_three_target_training(self) -> bool:
        return self.targets.ready_for_three_target_training


def build_white_balance_learning_target(
    *,
    targets: LightroomEditTargets,
    rendering_context: LightroomRenderingContext,
    mode: WhiteBalanceTargetMode,
) -> WhiteBalanceLearningTarget:
    if targets.temperature_k is None or targets.tint is None:
        raise ValueError("temperature_k and tint are required to build a WB learning target")

    if mode is WhiteBalanceTargetMode.ABSOLUTE_KELVIN:
        return WhiteBalanceLearningTarget(
            mode=mode,
            temperature=targets.temperature_k,
            tint=targets.tint,
        )

    if not rendering_context.wb_mapping_reliable:
        raise ValueError("delta_from_as_shot requires wb_mapping_reliable=True")
    if (
        rendering_context.as_shot_temperature_k is None
        or rendering_context.as_shot_tint is None
    ):
        raise ValueError("delta_from_as_shot requires As Shot temperature and tint")

    return WhiteBalanceLearningTarget(
        mode=mode,
        temperature=targets.temperature_k - rendering_context.as_shot_temperature_k,
        tint=targets.tint - rendering_context.as_shot_tint,
    )
