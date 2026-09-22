from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

from app.brain_v2.preprocessing.raw_decode import DecodedRawFrame


DetectionState = Literal["available", "not_detected", "unavailable"]
RegionKind = Literal["face", "skin", "subject"]


@dataclass(frozen=True)
class NormalizedBox:
    x: float
    y: float
    width: float
    height: float
    confidence: float

    def validate(self) -> None:
        for name, value in (
            ("x", self.x),
            ("y", self.y),
            ("width", self.width),
            ("height", self.height),
            ("confidence", self.confidence),
        ):
            if not np.isfinite(value):
                raise ValueError(f"{name} חייב להיות מספר סופי.")
        if not 0.0 <= self.x <= 1.0:
            raise ValueError("x מחוץ לטווח 0..1.")
        if not 0.0 <= self.y <= 1.0:
            raise ValueError("y מחוץ לטווח 0..1.")
        if not 0.0 < self.width <= 1.0:
            raise ValueError("width מחוץ לטווח.")
        if not 0.0 < self.height <= 1.0:
            raise ValueError("height מחוץ לטווח.")
        if self.x + self.width > 1.000001:
            raise ValueError("הקופסה חורגת מרוחב התמונה.")
        if self.y + self.height > 1.000001:
            raise ValueError("הקופסה חורגת מגובה התמונה.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence מחוץ לטווח 0..1.")


@dataclass(frozen=True)
class RegionDetection:
    kind: RegionKind
    box: NormalizedBox
    detector_id: str
    detector_version: str

    def validate(self) -> None:
        self.box.validate()
        if not self.detector_id.strip():
            raise ValueError("detector_id חסר.")
        if not self.detector_version.strip():
            raise ValueError("detector_version חסרה.")


@dataclass(frozen=True)
class RegionEvidence:
    state: DetectionState
    detections: tuple[RegionDetection, ...]
    detector_id: str | None
    detector_version: str | None
    reason: str | None = None

    def validate(self) -> None:
        if self.state == "unavailable":
            if self.detections:
                raise ValueError("unavailable אינו יכול להכיל detections.")
            if not self.reason:
                raise ValueError("unavailable חייב לכלול reason.")
            return

        if not self.detector_id or not self.detector_version:
            raise ValueError("Evidence זמין חייב detector + version.")

        for detection in self.detections:
            detection.validate()
            if detection.detector_id != self.detector_id:
                raise ValueError("detector_id אינו עקבי.")
            if detection.detector_version != self.detector_version:
                raise ValueError("detector_version אינו עקבי.")

        if self.state == "not_detected" and self.detections:
            raise ValueError("not_detected אינו יכול להכיל detections.")
        if self.state == "available" and not self.detections:
            raise ValueError("available מחייב detection אחד לפחות.")


class VisualRegionDetector(Protocol):
    def detect(self, frame: DecodedRawFrame) -> RegionEvidence:
        ...


class UnavailableVisualRegionDetector:
    def detect(self, frame: DecodedRawFrame) -> RegionEvidence:
        frame.validate()
        evidence = RegionEvidence(
            state="unavailable",
            detections=(),
            detector_id=None,
            detector_version=None,
            reason="No validated face/skin/subject detector is active.",
        )
        evidence.validate()
        return evidence


@dataclass(frozen=True)
class RegionSummary:
    available: float
    detected: float
    count: float
    max_confidence: float
    total_area_fraction: float
    largest_area_fraction: float
    center_x: float
    center_y: float
    luminance_mean: float
    luminance_p50: float
    shadow_fraction: float
    highlight_fraction: float
    red_mean: float
    green_mean: float
    blue_mean: float


FIELDS = (
    "available",
    "detected",
    "count",
    "max_confidence",
    "total_area_fraction",
    "largest_area_fraction",
    "center_x",
    "center_y",
    "luminance_mean",
    "luminance_p50",
    "shadow_fraction",
    "highlight_fraction",
    "red_mean",
    "green_mean",
    "blue_mean",
)


def _crop(rgb: np.ndarray, box: NormalizedBox) -> np.ndarray:
    h, w, _ = rgb.shape
    x0 = max(0, min(w - 1, int(round(box.x * w))))
    y0 = max(0, min(h - 1, int(round(box.y * h))))
    x1 = max(x0 + 1, min(w, int(round((box.x + box.width) * w))))
    y1 = max(y0 + 1, min(h, int(round((box.y + box.height) * h))))
    return rgb[y0:y1, x0:x1, :]


def _summary(frame: DecodedRawFrame, evidence: RegionEvidence, kind: RegionKind) -> RegionSummary:
    evidence.validate()

    if evidence.state == "unavailable":
        return RegionSummary(*(0.0 for _ in FIELDS))

    detections = tuple(d for d in evidence.detections if d.kind == kind)
    if not detections:
        return RegionSummary(
            1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        )

    boxes = [d.box for d in detections]
    largest = max(boxes, key=lambda b: b.width * b.height)
    pixels = np.concatenate(
        [_crop(frame.rgb_linear, b).reshape(-1, 3) for b in boxes],
        axis=0,
    ).astype(np.float64, copy=False)

    r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b

    return RegionSummary(
        available=1.0,
        detected=1.0,
        count=float(len(boxes)),
        max_confidence=float(max(box.confidence for box in boxes)),
        total_area_fraction=float(min(sum(box.width * box.height for box in boxes), 1.0)),
        largest_area_fraction=float(largest.width * largest.height),
        center_x=float(largest.x + largest.width / 2.0),
        center_y=float(largest.y + largest.height / 2.0),
        luminance_mean=float(np.mean(lum)),
        luminance_p50=float(np.percentile(lum, 50)),
        shadow_fraction=float(np.mean(lum <= 0.01)),
        highlight_fraction=float(np.mean(lum >= 0.98)),
        red_mean=float(np.mean(r)),
        green_mean=float(np.mean(g)),
        blue_mean=float(np.mean(b)),
    )


def visual_region_features(
    frame: DecodedRawFrame,
    evidence: RegionEvidence,
) -> tuple[tuple[str, ...], tuple[float, ...]]:
    frame.validate()
    evidence.validate()

    names: list[str] = []
    values: list[float] = []

    for kind in ("face", "skin", "subject"):
        summary = _summary(frame, evidence, kind)
        for field in FIELDS:
            names.append(f"region.{kind}.{field}")
            values.append(float(getattr(summary, field)))

    return tuple(names), tuple(values)
