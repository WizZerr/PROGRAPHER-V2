from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import statistics
import time
from typing import Any

from app.brain_v2.components import RawInputRecord
from app.brain_v2.contracts import CameraInfo
from app.brain_v2.features.rtdetr_person import YuNetRTDETRRegionDetector
from app.brain_v2.preprocessing.raw_pixels import RawPixelPreprocessor


RAW_EXTENSIONS = {
    ".3fr",
    ".arw",
    ".cr2",
    ".cr3",
    ".dng",
    ".erf",
    ".iiq",
    ".kdc",
    ".mos",
    ".mrw",
    ".nef",
    ".nrw",
    ".orf",
    ".pef",
    ".raf",
    ".raw",
    ".rw2",
    ".srw",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iou(a: dict[str, float], b: dict[str, float]) -> float:
    ax0 = a["x"]
    ay0 = a["y"]
    ax1 = a["x"] + a["width"]
    ay1 = a["y"] + a["height"]

    bx0 = b["x"]
    by0 = b["y"]
    bx1 = b["x"] + b["width"]
    by1 = b["y"] + b["height"]

    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)

    iw = max(0.0, ix1 - ix0)
    ih = max(0.0, iy1 - iy0)
    intersection = iw * ih
    if intersection <= 0.0:
        return 0.0

    area_a = max(0.0, a["width"]) * max(0.0, a["height"])
    area_b = max(0.0, b["width"]) * max(0.0, b["height"])
    union = area_a + area_b - intersection
    if union <= 0.0:
        return 0.0
    return intersection / union


def _serialize_detection(item: Any) -> dict[str, Any]:
    return {
        "kind": item.kind,
        "confidence": float(item.box.confidence),
        "box": {
            "x": float(item.box.x),
            "y": float(item.box.y),
            "width": float(item.box.width),
            "height": float(item.box.height),
        },
    }


def _serialize_evidence(evidence: Any) -> dict[str, Any]:
    return {
        "state": evidence.state,
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
            _serialize_detection(item)
            for item in evidence.detections
        ],
    }


def _detections_for_kind(
    evidence: dict[str, Any],
    kind: str,
) -> list[dict[str, Any]]:
    return [
        item
        for item in evidence["detections"]
        if item["kind"] == kind
    ]


def _match_detections(
    cpu: list[dict[str, Any]],
    cuda: list[dict[str, Any]],
    *,
    min_iou: float,
    max_confidence_diff: float,
) -> dict[str, Any]:
    if len(cpu) != len(cuda):
        return {
            "consistent": False,
            "reason": "count_mismatch",
            "cpu_count": len(cpu),
            "cuda_count": len(cuda),
            "matches": [],
        }

    candidates: list[tuple[float, int, int]] = []
    for cpu_index, cpu_item in enumerate(cpu):
        for cuda_index, cuda_item in enumerate(cuda):
            candidates.append(
                (
                    _iou(cpu_item["box"], cuda_item["box"]),
                    cpu_index,
                    cuda_index,
                )
            )

    candidates.sort(reverse=True)
    used_cpu: set[int] = set()
    used_cuda: set[int] = set()
    matches: list[dict[str, Any]] = []

    for iou_value, cpu_index, cuda_index in candidates:
        if cpu_index in used_cpu or cuda_index in used_cuda:
            continue
        used_cpu.add(cpu_index)
        used_cuda.add(cuda_index)

        cpu_item = cpu[cpu_index]
        cuda_item = cuda[cuda_index]
        confidence_diff = abs(
            float(cpu_item["confidence"])
            - float(cuda_item["confidence"])
        )
        match_ok = (
            iou_value >= min_iou
            and confidence_diff <= max_confidence_diff
        )
        matches.append(
            {
                "cpu_index": cpu_index,
                "cuda_index": cuda_index,
                "iou": iou_value,
                "confidence_diff": confidence_diff,
                "consistent": match_ok,
            }
        )

    complete = (
        len(used_cpu) == len(cpu)
        and len(used_cuda) == len(cuda)
    )
    all_ok = complete and all(item["consistent"] for item in matches)

    return {
        "consistent": all_ok,
        "reason": None if all_ok else "box_or_confidence_tolerance",
        "cpu_count": len(cpu),
        "cuda_count": len(cuda),
        "matches": sorted(matches, key=lambda item: item["cpu_index"]),
    }


def _compare_evidence(
    cpu: dict[str, Any],
    cuda: dict[str, Any],
    *,
    min_iou: float,
    max_confidence_diff: float,
) -> dict[str, Any]:
    state_checks = {}
    for kind in ("face", "skin", "subject"):
        cpu_state = cpu["per_kind"][kind]["state"]
        cuda_state = cuda["per_kind"][kind]["state"]
        state_checks[kind] = {
            "cpu": cpu_state,
            "cuda": cuda_state,
            "equal": cpu_state == cuda_state,
        }

    kind_matches = {
        kind: _match_detections(
            _detections_for_kind(cpu, kind),
            _detections_for_kind(cuda, kind),
            min_iou=min_iou,
            max_confidence_diff=max_confidence_diff,
        )
        for kind in ("face", "subject")
    }

    consistent = (
        all(item["equal"] for item in state_checks.values())
        and all(item["consistent"] for item in kind_matches.values())
    )

    return {
        "consistent": consistent,
        "state_checks": state_checks,
        "detection_checks": kind_matches,
    }


def _collect_raws(folder: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in folder.rglob("*")
            if path.is_file()
            and path.suffix.lower() in RAW_EXTENSIONS
        ),
        key=lambda path: str(path).lower(),
    )


def _spread_sample(paths: list[Path], limit: int) -> list[Path]:
    if limit <= 0 or len(paths) <= limit:
        return paths
    if limit == 1:
        return [paths[len(paths) // 2]]

    indices = [
        round(index * (len(paths) - 1) / (limit - 1))
        for index in range(limit)
    ]
    result = []
    seen = set()
    for index in indices:
        path = paths[index]
        if path not in seen:
            result.append(path)
            seen.add(path)
    return result


def _unique_paths(paths: list[Path]) -> list[Path]:
    result = []
    seen = set()
    for path in paths:
        resolved = path.resolve()
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(resolved)
    return result


def _build_raw_record(path: Path, index: int) -> RawInputRecord:
    return RawInputRecord(
        source_fingerprint=f"sha256:{_sha256(path)}",
        event_id=f"phase11-multi-raw-{index:03d}",
        camera=CameraInfo(),
        captured_at=None,
        raw_wb=None,
        exif={},
        missing_fields=("camera_model", "captured_at", "raw_wb"),
        raw_path=str(path),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Extra RAW path to always include. Repeatable.",
    )
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--min-iou", type=float, default=0.98)
    parser.add_argument("--max-confidence-diff", type=float, default=0.01)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    backend = Path.cwd().resolve()
    if not (backend / "app" / "brain_v2").is_dir():
        raise SystemExit(
            f"Run from the ProGrapher V2 backend directory. Current: {backend}"
        )

    folder = args.folder.resolve()
    if not folder.is_dir():
        raise SystemExit(f"RAW folder not found: {folder}")

    try:
        import torch
    except Exception as exc:
        raise SystemExit(f"PyTorch unavailable: {type(exc).__name__}: {exc}")

    if not torch.cuda.is_available():
        raise SystemExit(
            "CUDA is unavailable. This Windows CPU↔CUDA comparison requires CUDA."
        )

    discovered = _collect_raws(folder)
    if not discovered:
        raise SystemExit(f"No supported RAW files found under: {folder}")

    selected = _spread_sample(discovered, max(1, args.limit))

    extra_paths = [Path(value).resolve() for value in args.include]
    missing_extra = [str(path) for path in extra_paths if not path.is_file()]
    if missing_extra:
        raise SystemExit(
            "Included RAW path(s) not found:\n" + "\n".join(missing_extra)
        )

    samples = _unique_paths(selected + extra_paths)

    face_model = (
        backend
        / "vendor"
        / "opencv_zoo"
        / "face_detection_yunet"
        / "face_detection_yunet_2026may.onnx"
    )
    person_model = (
        backend
        / "vendor"
        / "huggingface"
        / "PekingU_rtdetr_r50vd"
    )

    cpu_detector = YuNetRTDETRRegionDetector(
        face_model_path=face_model,
        person_model_path=person_model,
        person_threshold=args.threshold,
        device="cpu",
    )
    cuda_detector = YuNetRTDETRRegionDetector(
        face_model_path=face_model,
        person_model_path=person_model,
        person_threshold=args.threshold,
        device="cuda",
    )
    preprocessor = RawPixelPreprocessor()

    rows: list[dict[str, Any]] = []
    cpu_times: list[float] = []
    cuda_times: list[float] = []

    print(
        f"Found {len(discovered)} RAW files; "
        f"selected {len(samples)} for deterministic comparison."
    )

    for index, raw_path in enumerate(samples, start=1):
        print(f"[{index}/{len(samples)}] {raw_path.name}")
        row: dict[str, Any] = {
            "path": str(raw_path),
            "sha256": _sha256(raw_path),
        }

        try:
            preprocess_started = time.perf_counter()
            preprocessed = preprocessor.run(
                _build_raw_record(raw_path, index)
            )
            preprocess_seconds = time.perf_counter() - preprocess_started

            cpu_started = time.perf_counter()
            cpu_evidence = cpu_detector.detect(preprocessed.decoded_frame)
            cpu_seconds = time.perf_counter() - cpu_started

            cuda_started = time.perf_counter()
            cuda_evidence = cuda_detector.detect(preprocessed.decoded_frame)
            cuda_seconds = time.perf_counter() - cuda_started

            cpu_serialized = _serialize_evidence(cpu_evidence)
            cuda_serialized = _serialize_evidence(cuda_evidence)
            comparison = _compare_evidence(
                cpu_serialized,
                cuda_serialized,
                min_iou=args.min_iou,
                max_confidence_diff=args.max_confidence_diff,
            )

            row.update(
                {
                    "status": "ok",
                    "preprocess_seconds": preprocess_seconds,
                    "cpu_seconds": cpu_seconds,
                    "cuda_seconds": cuda_seconds,
                    "cpu": cpu_serialized,
                    "cuda": cuda_serialized,
                    "comparison": comparison,
                }
            )
            cpu_times.append(cpu_seconds)
            cuda_times.append(cuda_seconds)

            print(
                f"  consistent={comparison['consistent']} "
                f"cpu={cpu_seconds:.3f}s cuda={cuda_seconds:.3f}s "
                f"face={cpu_serialized['per_kind']['face']['detections']} "
                f"subject={cpu_serialized['per_kind']['subject']['detections']}"
            )
        except Exception as exc:
            row.update(
                {
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "comparison": {"consistent": False},
                }
            )
            print(f"  ERROR: {row['error']}")

        rows.append(row)

        # Release the full decoded RAW before the next sample.
        if "preprocessed" in locals():
            del preprocessed
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    successful = [row for row in rows if row["status"] == "ok"]
    consistent_count = sum(
        1
        for row in successful
        if row["comparison"]["consistent"]
    )
    error_count = sum(1 for row in rows if row["status"] == "error")
    mismatch_count = len(successful) - consistent_count

    overall_pass = (
        error_count == 0
        and mismatch_count == 0
        and len(successful) == len(rows)
    )

    report = {
        "schema_version": "phase11-multi-raw-detector-consistency-v1",
        "source_folder": str(folder),
        "source_raw_count": len(discovered),
        "sample_selection": {
            "mode": "deterministic_spread_plus_explicit_includes",
            "requested_folder_limit": args.limit,
            "selected_count": len(samples),
            "paths": [str(path) for path in samples],
        },
        "tolerances": {
            "min_iou": args.min_iou,
            "max_confidence_diff": args.max_confidence_diff,
            "person_threshold": args.threshold,
        },
        "summary": {
            "overall_pass": overall_pass,
            "samples": len(rows),
            "successful": len(successful),
            "consistent": consistent_count,
            "mismatched": mismatch_count,
            "errors": error_count,
            "cpu_detector_median_seconds": (
                statistics.median(cpu_times) if cpu_times else None
            ),
            "cuda_detector_median_seconds": (
                statistics.median(cuda_times) if cuda_times else None
            ),
        },
        "samples": rows,
        "interpretation_limits": [
            "This validates CPU↔CUDA consistency only on the selected RAW fixture.",
            "It is not an event-editing quality comparison.",
            "It does not substitute for the blocked Dataset V2 feature-ablation work.",
            "macOS/MPS remains untested until a real Apple Silicon Mac is available.",
        ],
    }

    output = (
        args.output.resolve()
        if args.output
        else backend.parent
        / "docs"
        / "runtime"
        / "phase11_multi_raw_detector_consistency.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=== Phase 11 multi-RAW CPU↔CUDA consistency ===")
    print(
        f"samples={len(rows)} consistent={consistent_count} "
        f"mismatched={mismatch_count} errors={error_count}"
    )
    if cpu_times:
        print(f"CPU median detector time: {statistics.median(cpu_times):.4f}s")
    if cuda_times:
        print(f"CUDA median detector time: {statistics.median(cuda_times):.4f}s")
    print(f"OVERALL PASS: {overall_pass}")
    print(f"Report: {output}")

    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
