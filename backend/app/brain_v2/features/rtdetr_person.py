from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.brain_v2.features.opencv_regions import (
    OpenCVEventRegionDetector,
    _linear_to_bgr8,
)
from app.brain_v2.features.visual_regions import (
    RegionDetection,
    RegionEvidence,
    RegionKindStatus,
)
from app.brain_v2.preprocessing.raw_decode import DecodedRawFrame


DETECTOR_ID = "yunet-rtdetr-person"
DETECTOR_VERSION = "yunet-2026may+rtdetr-r50vd+impl-v1"


def _device_name(torch_module: Any) -> str:
    if torch_module.cuda.is_available():
        return "cuda"
    mps = getattr(torch_module.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def _is_person_label(label: object) -> bool:
    return str(label).strip().lower() == "person"


class RTDETRPersonDetector:
    def __init__(
        self,
        *,
        model_path: str | Path,
        threshold: float = 0.70,
        device: str | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.threshold = float(threshold)
        self.requested_device = device
        self._processor: Any | None = None
        self._model: Any | None = None
        self._torch: Any | None = None
        self._device: str | None = None

    @property
    def device(self) -> str | None:
        return self._device

    def _load(self) -> tuple[Any, Any, Any, str]:
        if not self.model_path.is_dir():
            raise FileNotFoundError(
                f"RT-DETR model directory is missing: {self.model_path}"
            )

        if self._model is not None:
            assert self._processor is not None
            assert self._torch is not None
            assert self._device is not None
            return self._torch, self._processor, self._model, self._device

        import torch
        from transformers import AutoImageProcessor, AutoModelForObjectDetection

        device = self.requested_device or _device_name(torch)
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is unavailable.")
        if device == "mps":
            mps = getattr(torch.backends, "mps", None)
            if mps is None or not mps.is_available():
                raise RuntimeError("MPS was requested but is unavailable.")
        if device not in {"cpu", "cuda", "mps"}:
            raise ValueError(f"Unsupported device: {device}")

        processor = AutoImageProcessor.from_pretrained(
            str(self.model_path),
            local_files_only=True,
            use_fast=False,
        )
        model = AutoModelForObjectDetection.from_pretrained(
            str(self.model_path),
            local_files_only=True,
            use_safetensors=True,
        )
        model.eval()
        model.to(device)

        self._torch = torch
        self._processor = processor
        self._model = model
        self._device = device
        return torch, processor, model, device

    def detect_subjects(
        self,
        frame: DecodedRawFrame,
    ) -> tuple[RegionKindStatus, tuple[RegionDetection, ...]]:
        frame.validate()

        try:
            torch, processor, model, device = self._load()
        except Exception as exc:
            return (
                RegionKindStatus(
                    kind="subject",
                    state="unavailable",
                    reason=f"RT-DETR load error: {type(exc).__name__}: {exc}",
                ),
                (),
            )

        try:
            bgr = _linear_to_bgr8(frame.rgb_linear)
            rgb = np.ascontiguousarray(bgr[:, :, ::-1])
            height, width = rgb.shape[:2]

            inputs = processor(images=rgb, return_tensors="pt")
            inputs = {
                key: value.to(device)
                for key, value in inputs.items()
            }

            with torch.inference_mode():
                outputs = model(**inputs)

            target_sizes = torch.tensor(
                [[height, width]],
                device=outputs.logits.device,
            )
            result = processor.post_process_object_detection(
                outputs,
                threshold=self.threshold,
                target_sizes=target_sizes,
            )[0]

            id2label = model.config.id2label
            detections: list[RegionDetection] = []

            for score, label_id, box in zip(
                result["scores"],
                result["labels"],
                result["boxes"],
            ):
                label_value = int(label_id.detach().cpu().item())
                label_name = id2label.get(
                    label_value,
                    id2label.get(str(label_value), str(label_value)),
                )
                if not _is_person_label(label_name):
                    continue

                x0, y0, x1, y1 = [
                    float(value)
                    for value in box.detach().cpu().tolist()
                ]
                x0 = max(0.0, min(float(width - 1), x0))
                y0 = max(0.0, min(float(height - 1), y0))
                x1 = max(x0 + 1.0, min(float(width), x1))
                y1 = max(y0 + 1.0, min(float(height), y1))

                from app.brain_v2.features.visual_regions import NormalizedBox

                norm = NormalizedBox(
                    x=x0 / float(width),
                    y=y0 / float(height),
                    width=(x1 - x0) / float(width),
                    height=(y1 - y0) / float(height),
                    confidence=float(score.detach().cpu().item()),
                )
                norm.validate()

                detections.append(
                    RegionDetection(
                        kind="subject",
                        box=norm,
                        detector_id=DETECTOR_ID,
                        detector_version=DETECTOR_VERSION,
                    )
                )
        except Exception as exc:
            return (
                RegionKindStatus(
                    kind="subject",
                    state="unavailable",
                    reason=f"RT-DETR inference error: {type(exc).__name__}: {exc}",
                ),
                (),
            )

        if not detections:
            return RegionKindStatus(kind="subject", state="not_detected"), ()

        return (
            RegionKindStatus(kind="subject", state="available"),
            tuple(detections),
        )


class YuNetRTDETRRegionDetector:
    def __init__(
        self,
        *,
        face_model_path: str | Path,
        person_model_path: str | Path,
        person_threshold: float = 0.70,
        device: str | None = None,
    ) -> None:
        # The old PP-HumanSeg candidate is intentionally retained for comparison,
        # but this composite uses only its YuNet face path.
        self._yunet = OpenCVEventRegionDetector(
            face_model_path=face_model_path,
            subject_model_path=Path("__unused_pphumanseg_model__"),
        )
        self._person = RTDETRPersonDetector(
            model_path=person_model_path,
            threshold=person_threshold,
            device=device,
        )

    @property
    def person_device(self) -> str | None:
        return self._person.device

    def detect(self, frame: DecodedRawFrame) -> RegionEvidence:
        frame.validate()
        bgr = _linear_to_bgr8(frame.rgb_linear)

        face_status, old_face_detections = self._yunet._detect_faces(bgr)
        face_detections = tuple(
            RegionDetection(
                kind="face",
                box=detection.box,
                detector_id=DETECTOR_ID,
                detector_version=DETECTOR_VERSION,
            )
            for detection in old_face_detections
        )
        subject_status, subject_detections = self._person.detect_subjects(frame)

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
