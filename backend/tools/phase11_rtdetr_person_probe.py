from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time

from app.brain_v2.components import RawInputRecord
from app.brain_v2.contracts import CameraInfo
from app.brain_v2.features.rtdetr_person import YuNetRTDETRRegionDetector
from app.brain_v2.preprocessing.raw_pixels import RawPixelPreprocessor


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--device", default=None)
    parser.add_argument("--output", type=Path, default=None)
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
        event_id="phase11-rtdetr-probe",
        camera=CameraInfo(),
        captured_at=None,
        raw_wb=None,
        exif={},
        missing_fields=("camera_model", "captured_at", "raw_wb"),
        raw_path=str(raw_path),
    )
    preprocessed = RawPixelPreprocessor().run(source)

    detector = YuNetRTDETRRegionDetector(
        face_model_path=face_model,
        person_model_path=person_model,
        person_threshold=args.threshold,
        device=args.device,
    )

    times = []
    evidence = None
    for _ in range(max(1, args.runs)):
        start = time.perf_counter()
        evidence = detector.detect(preprocessed.decoded_frame)
        times.append(time.perf_counter() - start)

    assert evidence is not None
    report = {
        "source": str(raw_path),
        "detector": evidence.detector_id,
        "detector_version": evidence.detector_version,
        "person_device": detector.person_device,
        "threshold": args.threshold,
        "timing_seconds": {
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
        },
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
        "skin_color_threshold_heuristic_used": False,
    }

    print("\n=== Phase 11 RT-DETR person candidate probe ===")
    print(f"RAW: {raw_path}")
    print(f"Device: {detector.person_device}")
    print(f"Median detector time: {report['timing_seconds']['median']:.4f}s")
    for kind in ("face", "skin", "subject"):
        item = report["per_kind"][kind]
        print(
            f"{kind}: state={item['state']}, "
            f"detections={item['detections']}, reason={item['reason']}"
        )
    print("Subject semantics: COCO person class only")
    print("Skin color-threshold heuristic used: False")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Report: {args.output.resolve()}")

    if evidence.status_for("subject").state == "unavailable":
        return 3

    print("PASS: RT-DETR person runtime executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
