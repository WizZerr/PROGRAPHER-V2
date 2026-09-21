from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np


RAW_PREPROCESSING_VERSION = "raw-linear-srgb-v1"


@dataclass(frozen=True)
class RawDecodeConfig:
    use_camera_wb: bool = True
    use_auto_wb: bool = False
    no_auto_bright: bool = True
    gamma_power: float = 1.0
    gamma_slope: float = 1.0
    output_bps: int = 16
    output_color_space: str = "linear_srgb"
    demosaic_algorithm: str = "AHD"
    bright: float = 1.0

    def validate(self) -> None:
        if self.use_camera_wb and self.use_auto_wb:
            raise ValueError(
                "אי אפשר להשתמש ב-Camera WB וב-Auto WB באותו מסלול קבוע."
            )
        if not self.no_auto_bright:
            raise ValueError(
                "Auto Bright אסור במסלול הקלט הקבוע של Brain V2."
            )
        if self.gamma_power != 1.0 or self.gamma_slope != 1.0:
            raise ValueError(
                "Phase 11 v1 דורש gamma=(1,1) כדי לשמור פלט לינארי."
            )
        if self.output_bps != 16:
            raise ValueError(
                "Phase 11 v1 דורש פלט 16-bit לפני normalization."
            )
        if self.output_color_space != "linear_srgb":
            raise ValueError(
                "מרחב הצבע של Phase 11 v1 חייב להיות linear_srgb."
            )
        if self.demosaic_algorithm != "AHD":
            raise ValueError(
                "Demosaic algorithm שונה דורש גרסת preprocessing חדשה."
            )


@dataclass(frozen=True)
class RawDecodeMetadata:
    preprocessing_version: str
    raw_engine: str
    raw_engine_version: str
    numpy_version: str
    color_space: str
    bit_depth_before_normalization: int
    normalized_dtype: str
    width: int
    height: int
    raw_width: int | None
    raw_height: int | None
    orientation_flip: int | None
    camera_wb: tuple[float, ...] | None
    daylight_wb: tuple[float, ...] | None
    black_levels: tuple[float, ...] | None
    white_level: float | None
    config: RawDecodeConfig

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DecodedRawFrame:
    source_path: str
    source_sha256: str
    rgb_linear: np.ndarray
    metadata: RawDecodeMetadata

    def validate(self) -> None:
        if self.rgb_linear.ndim != 3 or self.rgb_linear.shape[2] != 3:
            raise ValueError("Decoded RAW חייב להיות RGB עם 3 ערוצים.")
        if self.rgb_linear.dtype != np.float32:
            raise ValueError("Decoded RAW חייב להיות float32.")
        if self.rgb_linear.size == 0:
            raise ValueError("Decoded RAW ריק.")
        if float(np.nanmin(self.rgb_linear)) < 0.0:
            raise ValueError("Decoded RAW מכיל ערכים מתחת ל-0.")
        if float(np.nanmax(self.rgb_linear)) > 1.0:
            raise ValueError("Decoded RAW מכיל ערכים מעל 1.")


class RawDecoderBackend(Protocol):
    def decode(
        self,
        raw_path: Path,
        config: RawDecodeConfig,
    ) -> DecodedRawFrame:
        ...


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _tuple_or_none(value: Any) -> tuple[float, ...] | None:
    if value is None:
        return None

    try:
        values = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None

    if not values:
        return None

    return values


class RawPyBackend:
    def decode(
        self,
        raw_path: Path,
        config: RawDecodeConfig,
    ) -> DecodedRawFrame:
        config.validate()

        try:
            import rawpy
        except ImportError as exc:
            raise RuntimeError(
                "rawpy אינו מותקן. התקן backend/requirements-phase11.txt."
            ) from exc

        source = raw_path.expanduser().resolve(strict=True)
        source_hash = _sha256(source)

        try:
            with rawpy.imread(str(source)) as raw:
                sizes = raw.sizes

                rgb16 = raw.postprocess(
                    use_camera_wb=config.use_camera_wb,
                    use_auto_wb=config.use_auto_wb,
                    no_auto_bright=config.no_auto_bright,
                    gamma=(config.gamma_power, config.gamma_slope),
                    output_bps=config.output_bps,
                    output_color=rawpy.ColorSpace.sRGB,
                    demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
                    bright=config.bright,
                )

                camera_wb = _tuple_or_none(
                    getattr(raw, "camera_whitebalance", None)
                )
                daylight_wb = _tuple_or_none(
                    getattr(raw, "daylight_whitebalance", None)
                )
                black_levels = _tuple_or_none(
                    getattr(raw, "black_level_per_channel", None)
                )
                white_level_value = getattr(raw, "white_level", None)
                white_level = (
                    float(white_level_value)
                    if white_level_value is not None
                    else None
                )

                raw_width = getattr(sizes, "raw_width", None)
                raw_height = getattr(sizes, "raw_height", None)
                flip = getattr(sizes, "flip", None)
        except Exception as exc:
            raise ValueError(
                f"LibRaw/rawpy לא הצליח לפענח את הקובץ: {source.name}"
            ) from exc

        if rgb16.dtype != np.uint16:
            raise ValueError(
                "rawpy החזיר dtype לא צפוי; preprocessing version חייב להיבדק."
            )

        rgb = rgb16.astype(np.float32) / np.float32(65535.0)

        metadata = RawDecodeMetadata(
            preprocessing_version=RAW_PREPROCESSING_VERSION,
            raw_engine="rawpy/libraw",
            raw_engine_version=str(rawpy.__version__),
            numpy_version=str(np.__version__),
            color_space="linear_srgb",
            bit_depth_before_normalization=16,
            normalized_dtype="float32",
            width=int(rgb.shape[1]),
            height=int(rgb.shape[0]),
            raw_width=int(raw_width) if raw_width is not None else None,
            raw_height=int(raw_height) if raw_height is not None else None,
            orientation_flip=int(flip) if flip is not None else None,
            camera_wb=camera_wb,
            daylight_wb=daylight_wb,
            black_levels=black_levels,
            white_level=white_level,
            config=config,
        )

        result = DecodedRawFrame(
            source_path=str(source),
            source_sha256=source_hash,
            rgb_linear=rgb,
            metadata=metadata,
        )
        result.validate()

        if _sha256(source) != source_hash:
            raise RuntimeError(
                "RAW המקור השתנה בזמן decode; הבדיקה נעצרה."
            )

        return result


def decode_raw(
    raw_path: str | Path,
    *,
    backend: RawDecoderBackend | None = None,
    config: RawDecodeConfig | None = None,
) -> DecodedRawFrame:
    source = Path(raw_path)
    active_backend = backend or RawPyBackend()
    active_config = config or RawDecodeConfig()
    return active_backend.decode(source, active_config)


def deterministic_sample(
    rgb: np.ndarray,
    *,
    max_pixels: int = 2_000_000,
) -> np.ndarray:
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("RGB sample חייב להיות HxWx3.")
    if max_pixels <= 0:
        raise ValueError("max_pixels חייב להיות חיובי.")

    total_pixels = rgb.shape[0] * rgb.shape[1]
    if total_pixels <= max_pixels:
        return rgb

    step = int(math.ceil(math.sqrt(total_pixels / max_pixels)))
    return rgb[::step, ::step, :]
