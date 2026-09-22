from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2 as cv
import numpy as np

from app.brain_v2.components import RawInputRecord
from app.brain_v2.contracts import CameraInfo
from app.brain_v2.features.opencv_regions import (
    OpenCVEventRegionDetector,
    _linear_to_bgr8,
)
from app.brain_v2.preprocessing.raw_pixels import RawPixelPreprocessor


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resize_for_output(image: np.ndarray, max_edge: int) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_edge:
        return image.copy(), 1.0

    scale = max_edge / float(longest)
    resized = cv.resize(
        image,
        (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
        interpolation=cv.INTER_AREA,
    )
    return resized, scale


def _draw_detection(
    canvas: np.ndarray,
    *,
    kind: str,
    x: float,
    y: float,
    width: float,
    height: float,
    confidence: float,
) -> None:
    h, w = canvas.shape[:2]
    x0 = max(0, min(w - 1, int(round(x * w))))
    y0 = max(0, min(h - 1, int(round(y * h))))
    x1 = max(x0 + 1, min(w - 1, int(round((x + width) * w))))
    y1 = max(y0 + 1, min(h - 1, int(round((y + height) * h))))

    # White outline for face, light gray for subject.
    color = (255, 255, 255) if kind == "face" else (190, 190, 190)
    thickness = max(2, int(round(max(h, w) / 700)))

    cv.rectangle(canvas, (x0, y0), (x1, y1), color, thickness)

    label = f"{kind} {confidence:.3f}"
    font_scale = max(0.45, min(1.2, max(h, w) / 1400.0))
    label_thickness = max(1, thickness - 1)
    (tw, th), baseline = cv.getTextSize(
        label,
        cv.FONT_HERSHEY_SIMPLEX,
        font_scale,
        label_thickness,
    )
    text_y = max(th + 4, y0 - 6)
    cv.rectangle(
        canvas,
        (x0, max(0, text_y - th - baseline - 4)),
        (min(w - 1, x0 + tw + 8), min(h - 1, text_y + baseline + 2)),
        (0, 0, 0),
        -1,
    )
    cv.putText(
        canvas,
        label,
        (x0 + 4, text_y),
        cv.FONT_HERSHEY_SIMPLEX,
        font_scale,
        color,
        label_thickness,
        cv.LINE_AA,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a visual overlay for Phase 11 face/subject detector validation."
    )
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--max-edge", type=int, default=1800)
    args = parser.parse_args()

    backend = Path.cwd().resolve()
    raw_path = args.raw.resolve()
    output_path = args.output.resolve()
    report_path = args.report.resolve() if args.report else None

    if not raw_path.is_file():
        raise SystemExit(f"RAW not found: {raw_path}")

    face_model = (
        backend
        / "vendor"
        / "opencv_zoo"
        / "face_detection_yunet"
        / "face_detection_yunet_2026may.onnx"
    )
    subject_model = (
        backend
        / "vendor"
        / "opencv_zoo"
        / "human_segmentation_pphumanseg"
        / "human_segmentation_pphumanseg_2023mar.onnx"
    )

    source = RawInputRecord(
        source_fingerprint=f"sha256:{_sha256(raw_path)}",
        event_id="phase11-region-visual-validation",
        camera=CameraInfo(),
        captured_at=None,
        raw_wb=None,
        exif={},
        missing_fields=("camera_model", "captured_at", "raw_wb"),
        raw_path=str(raw_path),
    )

    preprocessed = RawPixelPreprocessor().run(source)
    frame = preprocessed.decoded_frame
    if frame is None:
        raise SystemExit("Decoded RAW frame is unavailable.")

    detector = OpenCVEventRegionDetector(
        face_model_path=face_model,
        subject_model_path=subject_model,
    )
    evidence = detector.detect(frame)

    bgr = _linear_to_bgr8(frame.rgb_linear)
    canvas, _scale = _resize_for_output(bgr, max(200, args.max_edge))

    for detection in evidence.detections:
        _draw_detection(
            canvas,
            kind=detection.kind,
            x=detection.box.x,
            y=detection.box.y,
            width=detection.box.width,
            height=detection.box.height,
            confidence=detection.box.confidence,
        )

    lines = []
    for kind in ("face", "skin", "subject"):
        status = evidence.status_for(kind)
        count = sum(1 for d in evidence.detections if d.kind == kind)
        lines.append(f"{kind}: {status.state} | detections={count}")

    banner_height = 34 * len(lines) + 20
    banner = np.zeros((banner_height, canvas.shape[1], 3), dtype=np.uint8)
    for index, line in enumerate(lines):
        cv.putText(
            banner,
            line,
            (14, 30 + index * 34),
            cv.FONT_HERSHEY_SIMPLEX,
            0.72,
            (235, 235, 235),
            2,
            cv.LINE_AA,
        )

    final = np.vstack((banner, canvas))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv.imwrite(str(output_path), final):
        raise SystemExit(f"Could not write overlay: {output_path}")

    report = {
        "source": str(raw_path),
        "overlay": str(output_path),
        "per_kind": {
            kind: {
                "state": evidence.status_for(kind).state,
                "reason": evidence.status_for(kind).reason,
                "detections": sum(
                    1 for detection in evidence.detections if detection.kind == kind
                ),
            }
            for kind in ("face", "skin", "subject")
        },
        "detections": [
            {
                "kind": detection.kind,
                "confidence": detection.box.confidence,
                "box": {
                    "x": detection.box.x,
                    "y": detection.box.y,
                    "width": detection.box.width,
                    "height": detection.box.height,
                },
            }
            for detection in evidence.detections
        ],
        "skin_color_threshold_heuristic_used": False,
    }

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print("\n=== Phase 11 detector visual validation ===")
    print(f"Source: {raw_path}")
    for line in lines:
        print(line)
    print(f"Overlay: {output_path}")
    if report_path is not None:
        print(f"Report: {report_path}")
    print("PASS: visual validation artifact created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
