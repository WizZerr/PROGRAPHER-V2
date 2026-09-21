from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from app.brain_v2.contracts import FeatureVector
from app.brain_v2.preprocessing.raw_decode import (
    DecodedRawFrame,
    deterministic_sample,
)


PIXEL_FEATURE_VERSION = "pixel-stats-v1"


@dataclass(frozen=True)
class PixelStatistics:
    sampled_pixels: int
    luminance_mean: float
    luminance_std: float
    luminance_p01: float
    luminance_p05: float
    luminance_p50: float
    luminance_p95: float
    luminance_p99: float
    shadow_clip_fraction: float
    highlight_clip_fraction: float
    red_mean: float
    green_mean: float
    blue_mean: float
    red_p01: float
    red_p50: float
    red_p99: float
    green_p01: float
    green_p50: float
    green_p99: float
    blue_p01: float
    blue_p50: float
    blue_p99: float
    chroma_ratio_mean: float
    red_minus_blue_mean: float

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def compute_pixel_statistics(
    frame: DecodedRawFrame,
    *,
    max_pixels: int = 2_000_000,
) -> PixelStatistics:
    frame.validate()

    rgb = deterministic_sample(
        frame.rgb_linear,
        max_pixels=max_pixels,
    ).astype(np.float64, copy=False)

    flat = rgb.reshape(-1, 3)
    r = flat[:, 0]
    g = flat[:, 1]
    b = flat[:, 2]

    # Rec.709 coefficients applied to the documented linear-sRGB input.
    luminance = (
        0.2126 * r
        + 0.7152 * g
        + 0.0722 * b
    )

    maximum = np.max(flat, axis=1)
    minimum = np.min(flat, axis=1)
    chroma_ratio = (maximum - minimum) / np.maximum(maximum, 1e-8)

    def pct(values: np.ndarray, percentile: float) -> float:
        return float(np.percentile(values, percentile))

    return PixelStatistics(
        sampled_pixels=int(flat.shape[0]),
        luminance_mean=float(np.mean(luminance)),
        luminance_std=float(np.std(luminance)),
        luminance_p01=pct(luminance, 1),
        luminance_p05=pct(luminance, 5),
        luminance_p50=pct(luminance, 50),
        luminance_p95=pct(luminance, 95),
        luminance_p99=pct(luminance, 99),
        shadow_clip_fraction=float(np.mean(luminance <= 0.01)),
        highlight_clip_fraction=float(np.mean(luminance >= 0.98)),
        red_mean=float(np.mean(r)),
        green_mean=float(np.mean(g)),
        blue_mean=float(np.mean(b)),
        red_p01=pct(r, 1),
        red_p50=pct(r, 50),
        red_p99=pct(r, 99),
        green_p01=pct(g, 1),
        green_p50=pct(g, 50),
        green_p99=pct(g, 99),
        blue_p01=pct(b, 1),
        blue_p50=pct(b, 50),
        blue_p99=pct(b, 99),
        chroma_ratio_mean=float(np.mean(chroma_ratio)),
        red_minus_blue_mean=float(np.mean(r - b)),
    )


def pixel_statistics_feature_vector(
    stats: PixelStatistics,
) -> FeatureVector:
    payload = stats.to_dict()

    # sampled_pixels is diagnostic metadata, not a predictive feature.
    names = tuple(
        key
        for key in payload.keys()
        if key != "sampled_pixels"
    )
    values = tuple(float(payload[name]) for name in names)

    vector = FeatureVector(
        version=PIXEL_FEATURE_VERSION,
        values=values,
        feature_names=names,
    )
    vector.validate()
    return vector
