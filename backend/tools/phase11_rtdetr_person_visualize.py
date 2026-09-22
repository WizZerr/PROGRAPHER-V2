from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2 as cv
import numpy as np

from app.brain_v2.components import RawInputRecord
from app.brain_v2.contracts import CameraInfo
from app.brain_v2.features.opencv_regions import _linear_to_bgr8
from app.brain_v2.features.rtdetr_person import YuNetRTDETRRegionDetector
from app.brain_v2.preprocessing.raw_pixels import RawPixelPreprocessor


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resize(image: np.ndarray, max_edge: int) -> np.ndarray:
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_edge:
        return image.copy()
    scale = max_edge / float(longest)
    return cv.resize(
        image,
        (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
        interpolation=cv.INTER_AREA,
    )


def _draw(canvas: np.ndarray, detection) -> None:
    h, w = canvas.shape[:2]
    box = detection.box
    x0 = int(round(box.x * w))
    y0 = int(round(box.y * h))
    x1 = int(round((box.x + box.width) * w))
    y1 = int(round((box.y + box.height) * h))
    x0 = max(0, min(w - 1, x0))
    y0 = max(0, min(h - 1, y0))
    x1 = max(x0 + 1, min(w - 1, x1))
    y1 = max(y0 + 1, min(h - 1, y1))

    color = (255, 255, 255) if detection.kind == "face" else (190, 190, 190)
    thickness = max(2, int(round(max(h, w) / 700)))
    cv.rectangle(canvas, (x0, y0), (x1, y1), color, thickness)

    label = f"{detection.kind} {box.confidence:.3f}"
    cv.putText(
        canvas,
        label,
        (x0, max(24, y0 - 8)),
        cv.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        2,
        cv.LINE_AA,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--device", default=None)
    parser.add_argument("--max-edge", type=int, default=1800)
    args = parser.parse_args()

    backend = Path.cwd().resolve()
    raw_path = args.raw.resolve()
    if not raw_path.is_file():
        raise SystemExit(f"RAW not found: {raw_path}")

    face_model = (
        backend / "vendor" / "opencv_zoo" / "face_detection_yunet"
        / "face_detection_yunet_2026may.onnx"
    )
    person_model = (
        backend / "vendor" / "huggingface" / "PekingU_rtdetr_r50vd"
    )

    source = RawInputRecord(
        source_fingerprint=f"sha256:{_sha256(raw_path)}",
        event_id="phase11-rtdetr-visual",
        camera=CameraInfo(),
        captured_at=None,
        raw_wb=None,
        exif={},
        missing_fields=("camera_model", "captured_at", "raw_wb"),
        raw_path=str(raw_path),
    )
    pre = RawPixelPreprocessor().run(source)

    detector = YuNetRTDETRRegionDetector(
        face_model_path=face_model,
        person_model_path=person_model,
        person_threshold=args.threshold,
        device=args.device,
    )
    evidence = detector.detect(pre.decoded_frame)

    canvas = _resize(
        _linear_to_bgr8(pre.decoded_frame.rgb_linear),
        max(200, args.max_edge),
    )
    for detection in evidence.detections:
        _draw(canvas, detection)

    lines = []
    for kind in ("face", "skin", "subject"):
        status = evidence.status_for(kind)
        count = sum(1 for item in evidence.detections if item.kind == kind)
        lines.append(f"{kind}: {status.state} | detections={count}")

    banner = np.zeros((34 * len(lines) + 20, canvas.shape[1], 3), dtype=np.uint8)
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
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv.imwrite(str(output), final):
        raise SystemExit(f"Could not write: {output}")

    report = {
        "source": str(raw_path),
        "device": detector.person_device,
        "threshold": args.threshold,
        "per_kind": {
            kind: {
                "state": evidence.status_for(kind).state,
                "reason": evidence.status_for(kind).reason,
                "detections": sum(
                    1 for item in evidence.detections if item.kind == kind
                ),
            }
            for kind in ("face", "skin", "subject")
        },
        "detections": [
            {
                "kind": item.kind,
                "confidence": item.box.confidence,
                "box": {
                    "x": item.box.x,
                    "y": item.box.y,
                    "width": item.box.width,
                    "height": item.box.height,
                },
            }
            for item in evidence.detections
        ],
        "subject_semantics": "COCO person class only",
    }

    if args.report:
        report_path = args.report.resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print("\n=== Phase 11 RT-DETR visual validation ===")
    print(f"Source: {raw_path}")
    print(f"Device: {detector.person_device}")
    for line in lines:
        print(line)
    print(f"Overlay: {output}")
    if args.report:
        print(f"Report: {args.report.resolve()}")
    print("PASS: RT-DETR visual validation artifact created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
