from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any

import psutil


def _nvidia_total_used_mb() -> float | None:
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    values = []
    for line in result.stdout.splitlines():
        try:
            values.append(float(line.strip()))
        except ValueError:
            return None
    return sum(values) if values else None


def _rss_tree_mb(process: psutil.Process) -> float:
    total = 0
    try:
        total += process.memory_info().rss
        children = process.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0
    for child in children:
        try:
            total += child.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return total / (1024.0 * 1024.0)


def _worker(args: argparse.Namespace) -> int:
    from app.brain_v2.components import RawInputRecord
    from app.brain_v2.contracts import CameraInfo
    from app.brain_v2.features.rtdetr_person import YuNetRTDETRRegionDetector
    from app.brain_v2.preprocessing.raw_pixels import RawPixelPreprocessor

    backend = Path.cwd().resolve()
    raw = Path(args.raw).resolve()
    if not raw.is_file():
        raise SystemExit(f'RAW not found: {raw}')

    face_model = backend / 'vendor' / 'opencv_zoo' / 'face_detection_yunet' / 'face_detection_yunet_2026may.onnx'
    person_model = backend / 'vendor' / 'huggingface' / 'PekingU_rtdetr_r50vd'

    source = RawInputRecord(
        source_fingerprint='resource-benchmark',
        event_id=f'phase11-resource-{args.label}',
        camera=CameraInfo(),
        captured_at=None,
        raw_wb=None,
        exif={},
        missing_fields=('camera_model', 'captured_at', 'raw_wb'),
        raw_path=str(raw),
    )

    started = time.perf_counter()
    t0 = time.perf_counter()
    pre = RawPixelPreprocessor().run(source)
    decode_s = time.perf_counter() - t0

    detector = YuNetRTDETRRegionDetector(
        face_model_path=face_model,
        person_model_path=person_model,
        person_threshold=float(args.threshold),
        device=args.device,
    )

    t0 = time.perf_counter()
    evidence = detector.detect(pre.decoded_frame)
    cold_s = time.perf_counter() - t0

    times = []
    for _ in range(max(1, int(args.runs))):
        t0 = time.perf_counter()
        evidence = detector.detect(pre.decoded_frame)
        times.append(time.perf_counter() - t0)

    per_kind = {}
    for kind in ('face', 'skin', 'subject'):
        status = evidence.status_for(kind)
        per_kind[kind] = {
            'state': status.state,
            'reason': status.reason,
            'detections': sum(1 for d in evidence.detections if d.kind == kind),
        }

    expected_ok = True
    if args.label == 'negative':
        expected_ok = (
            per_kind['face']['state'] == 'not_detected'
            and per_kind['subject']['state'] == 'not_detected'
            and per_kind['subject']['detections'] == 0
        )
    elif args.label == 'positive':
        expected_ok = (
            per_kind['face']['state'] == 'available'
            and per_kind['face']['detections'] >= 1
            and per_kind['subject']['state'] == 'available'
            and per_kind['subject']['detections'] >= 1
        )

    report = {
        'label': args.label,
        'raw': str(raw),
        'requested_device': args.device,
        'actual_person_device': detector.person_device,
        'threshold': float(args.threshold),
        'runs': len(times),
        'timing_seconds': {
            'raw_preprocessing': decode_s,
            'cold_detector': cold_s,
            'steady_detector_median': statistics.median(times),
            'steady_detector_min': min(times),
            'steady_detector_max': max(times),
            'worker_total': time.perf_counter() - started,
        },
        'per_kind': per_kind,
        'expected_control_result': expected_ok,
        'subject_semantics': 'COCO person class only',
        'skin_color_threshold_heuristic_used': False,
    }

    out = Path(args.worker_output).resolve()
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'worker {args.label}/{args.device}: median={statistics.median(times):.4f}s expected_ok={expected_ok}')
    return 0 if expected_ok else 4


def _run_one(backend: Path, raw: Path, label: str, device: str, runs: int, threshold: float) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix='prographer-p11-resource-') as td:
        worker_out = Path(td) / 'worker.json'
        cmd = [
            sys.executable,
            '-m',
            'tools.phase11_detector_resource_benchmark',
            '--worker',
            '--raw', str(raw),
            '--label', label,
            '--device', device,
            '--runs', str(runs),
            '--threshold', str(threshold),
            '--worker-output', str(worker_out),
        ]

        gpu_base = _nvidia_total_used_mb() if device == 'cuda' else None
        gpu_peak = gpu_base
        start = time.perf_counter()
        proc = subprocess.Popen(
            cmd,
            cwd=str(backend),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        p = psutil.Process(proc.pid)
        peak_rss = 0.0

        while proc.poll() is None:
            peak_rss = max(peak_rss, _rss_tree_mb(p))
            if device == 'cuda':
                now = _nvidia_total_used_mb()
                if now is not None:
                    gpu_peak = now if gpu_peak is None else max(gpu_peak, now)
            time.sleep(0.05)

        stdout, stderr = proc.communicate()
        wall = time.perf_counter() - start
        if proc.returncode != 0:
            raise RuntimeError(
                f'worker failed label={label} device={device} rc={proc.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}'
            )
        report = json.loads(worker_out.read_text(encoding='utf-8'))
        report['monitoring'] = {
            'parent_wall_seconds': wall,
            'peak_process_tree_rss_mb': peak_rss,
            'gpu_memory_scope': 'system_total_nvidia_used_memory_delta' if device == 'cuda' else None,
            'gpu_total_used_baseline_mb': gpu_base,
            'gpu_total_used_peak_mb': gpu_peak,
            'gpu_total_used_peak_delta_mb': None if gpu_base is None or gpu_peak is None else gpu_peak - gpu_base,
        }
        report['worker_stderr'] = stderr.strip()
        return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--raw', type=Path)
    parser.add_argument('--label', choices=('negative', 'positive'))
    parser.add_argument('--device', choices=('cpu', 'cuda'))
    parser.add_argument('--worker-output', type=Path)
    parser.add_argument('--negative', type=Path)
    parser.add_argument('--positive', type=Path)
    parser.add_argument('--devices', default='cpu,cuda')
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--threshold', type=float, default=0.70)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()

    if args.worker:
        return _worker(args)

    backend = Path.cwd().resolve()
    if not (backend / 'app' / 'brain_v2').is_dir():
        raise SystemExit(f'Run from backend. Current: {backend}')
    if args.negative is None or args.positive is None:
        raise SystemExit('Use --negative and --positive.')

    negative = args.negative.resolve()
    positive = args.positive.resolve()
    for raw in (negative, positive):
        if not raw.is_file():
            raise SystemExit(f'RAW not found: {raw}')

    devices = [x.strip() for x in args.devices.split(',') if x.strip()]
    results = []
    for device in devices:
        if device not in {'cpu', 'cuda'}:
            raise SystemExit(f'Unsupported device: {device}')
        for label, raw in (('negative', negative), ('positive', positive)):
            print(f'Running {label} control on {device}...')
            row = _run_one(backend, raw, label, device, max(1, args.runs), args.threshold)
            results.append(row)
            print(f"  steady median: {row['timing_seconds']['steady_detector_median']:.4f}s")
            print(f"  peak RSS: {row['monitoring']['peak_process_tree_rss_mb']:.1f} MB")
            if device == 'cuda':
                print(f"  NVIDIA total-used delta: {row['monitoring']['gpu_total_used_peak_delta_mb']} MB")

    summary = {}
    for device in devices:
        rows = [r for r in results if r['requested_device'] == device]
        summary[device] = {
            'all_controls_expected_ok': all(r['expected_control_result'] for r in rows),
            'steady_detector_median_seconds_across_controls': statistics.median(r['timing_seconds']['steady_detector_median'] for r in rows),
            'max_peak_process_tree_rss_mb': max(r['monitoring']['peak_process_tree_rss_mb'] for r in rows),
            'max_gpu_total_used_peak_delta_mb': max((r['monitoring']['gpu_total_used_peak_delta_mb'] for r in rows if r['monitoring']['gpu_total_used_peak_delta_mb'] is not None), default=None),
        }

    report = {
        'schema_version': 'phase11-detector-resource-benchmark-v1',
        'runs_per_control_after_cold_run': max(1, args.runs),
        'negative_control': str(negative),
        'positive_control': str(positive),
        'results': results,
        'summary_by_device': summary,
        'interpretation_limits': [
            'Two RAW controls are not representative production throughput evidence.',
            'GPU memory is system-total NVIDIA used-memory delta, not isolated per-process VRAM.',
            'Cold timing includes first model load/inference effects.',
            'Steady timing reuses the loaded detector in one worker.',
            'macOS/MPS remains untested.',
            'Feature-group quality contribution remains blocked by a representative Dataset V2.',
        ],
    }

    out = args.output.resolve() if args.output else backend.parent / 'docs' / 'runtime' / 'phase11_detector_resource_benchmark.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    print('\n=== Phase 11 detector resource benchmark ===')
    for device, item in summary.items():
        print(
            f"{device}: steady_median={item['steady_detector_median_seconds_across_controls']:.4f}s | "
            f"peak_rss={item['max_peak_process_tree_rss_mb']:.1f}MB | "
            f"controls_ok={item['all_controls_expected_ok']}"
        )
        if device == 'cuda':
            print(f"  max NVIDIA total-used delta: {item['max_gpu_total_used_peak_delta_mb']} MB")
    print(f'Report: {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
