from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time

from app.brain_v2.components import RawInputRecord
from app.brain_v2.contracts import CameraInfo
from app.brain_v2.features.opencv_regions import OpenCVEventRegionDetector
from app.brain_v2.features.visual_regions import visual_region_features
from app.brain_v2.preprocessing.raw_pixels import RawPixelPreprocessor


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _box_dict(detection):
    box = detection.box
    return {
        "kind": detection.kind,
        "x": box.x,
        "y": box.y,
        "width": box.width,
        "height": box.height,
        "confidence": box.confidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    backend = Path.cwd().resolve()
    raw_path = args.raw.resolve()
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
        event_id="phase11-region-probe",
        camera=CameraInfo(),
        captured_at=None,
        raw_wb=None,
        exif={},
        missing_fields=("camera_model", "captured_at", "raw_wb"),
        raw_path=str(raw_path),
    )
    preprocessed = RawPixelPreprocessor().run(source)

    detector = OpenCVEventRegionDetector(
        face_model_path=face_model,
        subject_model_path=subject_model,
    )

    run_times = []
    evidence = None
    for _ in range(max(1, args.runs)):
        started = time.perf_counter()
        evidence = detector.detect(preprocessed.decoded_frame)
        run_times.append(time.perf_counter() - started)

    assert evidence is not None
    names, values = visual_region_features(
        preprocessed.decoded_frame,
        evidence,
    )
    feature_map = dict(zip(names, values))

    report = {
        "source": str(raw_path),
        "runs": len(run_times),
        "timing_seconds": {
            "median": statistics.median(run_times),
            "min": min(run_times),
            "max": max(run_times),
        },
        "evidence": {
            "state": evidence.state,
            "detector_id": evidence.detector_id,
            "detector_version": evidence.detector_version,
            "per_kind": {
                kind: {
                    "state": evidence.status_for(kind).state,
                    "reason": evidence.status_for(kind).reason,
                }
                for kind in ("face", "skin", "subject")
            },
            "detections": [_box_dict(item) for item in evidence.detections],
        },
        "region_flags": {
            key: value
            for key, value in feature_map.items()
            if key.endswith(".available")
            or key.endswith(".detected")
            or key.endswith(".count")
        },
        "skin_color_threshold_heuristic_used": False,
    }

    print("\n=== Phase 11 OpenCV region candidate probe ===")
    print(f"RAW: {raw_path}")
    print(f"Median detector time: {report['timing_seconds']['median']:.4f}s")
    for kind in ("face", "skin", "subject"):
        status = evidence.status_for(kind)
        count = sum(1 for item in evidence.detections if item.kind == kind)
        print(
            f"{kind}: state={status.state}, detections={count}, "
            f"reason={status.reason}"
        )
    print("Skin color-threshold heuristic used: False")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Report: {args.output.resolve()}")

    if evidence.status_for("face").state == "unavailable":
        return 2
    if evidence.status_for("subject").state == "unavailable":
        return 3

    print("PASS: face and subject detector runtimes executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
