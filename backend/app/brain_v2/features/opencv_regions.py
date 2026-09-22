from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.brain_v2.features.visual_regions import (
    NormalizedBox,
    RegionDetection,
    RegionEvidence,
    RegionKindStatus,
)
from app.brain_v2.preprocessing.raw_decode import DecodedRawFrame


DETECTOR_ID = "opencv-yunet-pphumanseg"
DETECTOR_VERSION = "yunet-2026may+pphumanseg-2023mar+impl-v1"


def _linear_to_bgr8(rgb_linear: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb_linear, dtype=np.float32)
    rgb = np.clip(rgb, 0.0, 1.0)

    encoded = np.where(
        rgb <= 0.0031308,
        rgb * 12.92,
        1.055 * np.power(rgb, 1.0 / 2.4) - 0.055,
    )
    rgb8 = np.rint(np.clip(encoded, 0.0, 1.0) * 255.0).astype(np.uint8)
    return np.ascontiguousarray(rgb8[:, :, ::-1])


def _normalized_box(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    image_width: int,
    image_height: int,
    confidence: float,
) -> NormalizedBox | None:
    if image_width <= 0 or image_height <= 0:
        return None

    x0 = max(0.0, min(float(image_width - 1), float(x)))
    y0 = max(0.0, min(float(image_height - 1), float(y)))
    x1 = max(x0 + 1.0, min(float(image_width), float(x) + float(width)))
    y1 = max(y0 + 1.0, min(float(image_height), float(y) + float(height)))

    norm = NormalizedBox(
        x=x0 / float(image_width),
        y=y0 / float(image_height),
        width=(x1 - x0) / float(image_width),
        height=(y1 - y0) / float(image_height),
        confidence=float(max(0.0, min(1.0, confidence))),
    )
    norm.validate()
    return norm


def _softmax_foreground(output: np.ndarray) -> np.ndarray:
    arr = np.asarray(output, dtype=np.float32)
    if arr.ndim != 4 or arr.shape[0] != 1 or arr.shape[1] < 2:
        raise ValueError(
            f"Unexpected PP-HumanSeg output shape: {tuple(arr.shape)}"
        )

    logits = arr[0, :2, :, :]
    shifted = logits - np.max(logits, axis=0, keepdims=True)
    exp = np.exp(shifted)
    denom = np.sum(exp, axis=0)
    return exp[1] / np.maximum(denom, 1e-12)


class OpenCVEventRegionDetector:
    def __init__(
        self,
        *,
        face_model_path: str | Path,
        subject_model_path: str | Path,
        face_score_threshold: float = 0.85,
        face_nms_threshold: float = 0.3,
        face_top_k: int = 5000,
        face_max_edge_px: int = 1600,
        subject_min_area_fraction: float = 0.001,
        subject_max_components: int = 20,
    ) -> None:
        self.face_model_path = Path(face_model_path)
        self.subject_model_path = Path(subject_model_path)
        self.face_score_threshold = float(face_score_threshold)
        self.face_nms_threshold = float(face_nms_threshold)
        self.face_top_k = int(face_top_k)
        self.face_max_edge_px = int(face_max_edge_px)
        self.subject_min_area_fraction = float(subject_min_area_fraction)
        self.subject_max_components = int(subject_max_components)

        self._cv: Any | None = None
        self._face_detector: Any | None = None
        self._subject_net: Any | None = None

    def _import_cv(self) -> Any:
        if self._cv is None:
            import cv2 as cv
            self._cv = cv
        return self._cv

    def _face_preview(self, bgr: np.ndarray) -> np.ndarray:
        cv = self._import_cv()
        h, w = bgr.shape[:2]
        longest = max(h, w)
        if longest <= self.face_max_edge_px:
            return bgr

        scale = self.face_max_edge_px / float(longest)
        target = (
            max(1, int(round(w * scale))),
            max(1, int(round(h * scale))),
        )
        return cv.resize(bgr, target, interpolation=cv.INTER_AREA)

    def _detect_faces(
        self,
        bgr: np.ndarray,
    ) -> tuple[RegionKindStatus, tuple[RegionDetection, ...]]:
        if not self.face_model_path.is_file():
            return (
                RegionKindStatus(
                    kind="face",
                    state="unavailable",
                    reason="YuNet model file is missing.",
                ),
                (),
            )

        try:
            cv = self._import_cv()
            preview = self._face_preview(bgr)
            h, w = preview.shape[:2]

            if self._face_detector is None:
                self._face_detector = cv.FaceDetectorYN.create(
                    str(self.face_model_path),
                    "",
                    (320, 320),
                    self.face_score_threshold,
                    self.face_nms_threshold,
                    self.face_top_k,
                )

            self._face_detector.setInputSize((w, h))
            _, faces = self._face_detector.detect(preview)
        except Exception as exc:
            return (
                RegionKindStatus(
                    kind="face",
                    state="unavailable",
                    reason=f"YuNet runtime error: {type(exc).__name__}: {exc}",
                ),
                (),
            )

        if faces is None or len(faces) == 0:
            return RegionKindStatus(kind="face", state="not_detected"), ()

        detections: list[RegionDetection] = []
        for row in np.asarray(faces):
            if len(row) < 5:
                continue

            confidence = float(row[-1])
            box = _normalized_box(
                x=float(row[0]),
                y=float(row[1]),
                width=float(row[2]),
                height=float(row[3]),
                image_width=w,
                image_height=h,
                confidence=confidence,
            )
            if box is None:
                continue

            detections.append(
                RegionDetection(
                    kind="face",
                    box=box,
                    detector_id=DETECTOR_ID,
                    detector_version=DETECTOR_VERSION,
                )
            )

        if not detections:
            return RegionKindStatus(kind="face", state="not_detected"), ()

        return (
            RegionKindStatus(kind="face", state="available"),
            tuple(detections),
        )

    def _detect_subjects(
        self,
        bgr: np.ndarray,
    ) -> tuple[RegionKindStatus, tuple[RegionDetection, ...]]:
        if not self.subject_model_path.is_file():
            return (
                RegionKindStatus(
                    kind="subject",
                    state="unavailable",
                    reason="PP-HumanSeg model file is missing.",
                ),
                (),
            )

        try:
            cv = self._import_cv()

            if self._subject_net is None:
                self._subject_net = cv.dnn.readNet(str(self.subject_model_path))

            rgb = cv.cvtColor(bgr, cv.COLOR_BGR2RGB)
            resized = cv.resize(rgb, (192, 192), interpolation=cv.INTER_LINEAR)
            normalized = resized.astype(np.float32, copy=False) / 255.0
            normalized = (normalized - 0.5) / 0.5
            blob = cv.dnn.blobFromImage(normalized)

            self._subject_net.setInput(blob)
            output = self._subject_net.forward()
            foreground = _softmax_foreground(output)
            mask = (foreground >= 0.5).astype(np.uint8)

            count, labels, stats, _ = cv.connectedComponentsWithStats(
                mask,
                connectivity=8,
            )
        except Exception as exc:
            return (
                RegionKindStatus(
                    kind="subject",
                    state="unavailable",
                    reason=(
                        "PP-HumanSeg runtime error: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                ),
                (),
            )

        height, width = mask.shape
        min_area = max(
            4,
            int(round(self.subject_min_area_fraction * width * height)),
        )

        components: list[tuple[int, int]] = []
        for label in range(1, count):
            area = int(stats[label, cv.CC_STAT_AREA])
            if area >= min_area:
                components.append((label, area))

        components.sort(key=lambda item: item[1], reverse=True)
        components = components[: self.subject_max_components]

        detections: list[RegionDetection] = []
        for label, _area in components:
            x = int(stats[label, cv.CC_STAT_LEFT])
            y = int(stats[label, cv.CC_STAT_TOP])
            w = int(stats[label, cv.CC_STAT_WIDTH])
            h = int(stats[label, cv.CC_STAT_HEIGHT])

            component_mask = labels == label
            confidence = float(np.mean(foreground[component_mask]))

            box = _normalized_box(
                x=x,
                y=y,
                width=w,
                height=h,
                image_width=width,
                image_height=height,
                confidence=confidence,
            )
            if box is None:
                continue

            detections.append(
                RegionDetection(
                    kind="subject",
                    box=box,
                    detector_id=DETECTOR_ID,
                    detector_version=DETECTOR_VERSION,
                )
            )

        if not detections:
            return RegionKindStatus(kind="subject", state="not_detected"), ()

        return (
            RegionKindStatus(kind="subject", state="available"),
            tuple(detections),
        )

    def detect(self, frame: DecodedRawFrame) -> RegionEvidence:
        frame.validate()
        bgr = _linear_to_bgr8(frame.rgb_linear)

        face_status, face_detections = self._detect_faces(bgr)
        subject_status, subject_detections = self._detect_subjects(bgr)

        skin_status = RegionKindStatus(
            kind="skin",
            state="unavailable",
            reason=(
                "No validated skin-region detector is active. "
                "Color-threshold skin heuristics are intentionally disabled."
            ),
        )

        detections = face_detections + subject_detections

        if detections:
            global_state = "available"
            reason = None
        elif (
            face_status.state == "unavailable"
            and subject_status.state == "unavailable"
        ):
            global_state = "unavailable"
            reason = "Face and subject detector runtimes are unavailable."
        else:
            global_state = "not_detected"
            reason = None

        evidence = RegionEvidence(
            state=global_state,
            detections=detections,
            detector_id=DETECTOR_ID,
            detector_version=DETECTOR_VERSION,
            reason=reason,
            kind_statuses=(
                face_status,
                skin_status,
                subject_status,
            ),
        )
        evidence.validate()
        return evidence
