from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

import psutil


def _query_nvidia_total_used_mb() -> float | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        cp = subprocess.run(
            [
                exe,
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        if cp.returncode != 0:
            return None
        values: list[float] = []
        for line in cp.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                values.append(float(line.split(",")[0].strip()))
            except ValueError:
                continue
        return sum(values) if values else None
    except Exception:
        return None


def _query_nvidia_process_memory_mb(pid: int) -> float | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        cp = subprocess.run(
            [
                exe,
                "--query-compute-apps=pid,used_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        if cp.returncode != 0:
            return None
        total = 0.0
        found = False
        for line in cp.stdout.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            try:
                row_pid = int(parts[0])
                mem = float(parts[1])
            except ValueError:
                continue
            if row_pid == pid:
                total += mem
                found = True
        return total if found else None
    except Exception:
        return None


def _process_tree_rss_mb(root_pid: int) -> float | None:
    try:
        proc = psutil.Process(root_pid)
        procs = [proc] + proc.children(recursive=True)
        rss = 0
        for p in procs:
            try:
                rss += p.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return rss / (1024 * 1024)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure wall time, peak RSS and NVIDIA VRAM while running the existing Phase 11 encoder benchmark."
    )
    parser.add_argument("--raw", required=True)
    parser.add_argument("--device", required=True, choices=["cpu", "cuda", "mps", "auto"])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--benchmark-script", default="tools/phase11_real_encoder_benchmark.py")
    parser.add_argument("--benchmark-output", required=True)
    parser.add_argument("--benchmark-vectors", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--samples-csv", default=None)
    parser.add_argument("--poll-ms", type=int, default=100)
    args = parser.parse_args()

    cmd = [
        sys.executable,
        args.benchmark_script,
        "--raw", args.raw,
        "--device", args.device,
        "--runs", str(args.runs),
        "--output", args.benchmark_output,
        "--vectors", args.benchmark_vectors,
    ]

    env = os.environ.copy()
    # Critical on Hebrew Windows CMD: force the child benchmark to emit UTF-8
    # so symbols such as ✅ do not crash under cp1255.
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    gpu_baseline_mb = _query_nvidia_total_used_mb() if args.device == "cuda" else None

    started = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )

    samples: list[dict[str, Any]] = []
    stdout_lines: list[str] = []

    def reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            stdout_lines.append(line)
            print(line, end="")

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    peak_rss_mb = 0.0
    peak_process_vram_mb: float | None = None
    peak_total_gpu_used_mb: float | None = gpu_baseline_mb
    poll_s = max(args.poll_ms, 20) / 1000.0

    while proc.poll() is None:
        elapsed = time.perf_counter() - started
        rss = _process_tree_rss_mb(proc.pid)

        process_vram = None
        total_gpu_used = None
        if args.device == "cuda":
            process_vram = _query_nvidia_process_memory_mb(proc.pid)
            total_gpu_used = _query_nvidia_total_used_mb()

        if rss is not None:
            peak_rss_mb = max(peak_rss_mb, rss)
        if process_vram is not None:
            peak_process_vram_mb = (
                process_vram if peak_process_vram_mb is None
                else max(peak_process_vram_mb, process_vram)
            )
        if total_gpu_used is not None:
            peak_total_gpu_used_mb = (
                total_gpu_used if peak_total_gpu_used_mb is None
                else max(peak_total_gpu_used_mb, total_gpu_used)
            )

        samples.append(
            {
                "elapsed_s": round(elapsed, 6),
                "rss_mb": rss,
                "nvidia_process_vram_mb": process_vram,
                "nvidia_total_gpu_used_mb": total_gpu_used,
            }
        )
        time.sleep(poll_s)

    reader_thread.join(timeout=5)
    return_code = proc.wait()
    wall_s = time.perf_counter() - started

    gpu_delta_mb = None
    if gpu_baseline_mb is not None and peak_total_gpu_used_mb is not None:
        gpu_delta_mb = max(0.0, peak_total_gpu_used_mb - gpu_baseline_mb)

    benchmark_json: dict[str, Any] | None = None
    benchmark_path = Path(args.benchmark_output)
    if benchmark_path.exists():
        try:
            benchmark_json = json.loads(benchmark_path.read_text(encoding="utf-8"))
        except Exception:
            benchmark_json = None

    report = {
        "schema_version": "phase11-resource-benchmark-v2",
        "device": args.device,
        "raw": str(Path(args.raw).resolve()),
        "python": sys.version,
        "command": cmd,
        "return_code": return_code,
        "wall_time_s": wall_s,
        "peak_process_tree_rss_mb": peak_rss_mb,
        "nvidia": {
            "baseline_total_used_mb": gpu_baseline_mb,
            "peak_total_used_mb": peak_total_gpu_used_mb,
            "peak_total_used_delta_mb": gpu_delta_mb,
            "peak_process_vram_mb": peak_process_vram_mb,
            "process_vram_note": (
                "May be unavailable under Windows/WDDM; total GPU memory delta is retained as fallback."
            ),
        },
        "poll_interval_ms": args.poll_ms,
        "sample_count": len(samples),
        "benchmark_report_path": str(benchmark_path.resolve()),
        "benchmark_vectors_path": str(Path(args.benchmark_vectors).resolve()),
        "benchmark_report": benchmark_json,
        "stdout": "".join(stdout_lines),
        "notes": [
            "Child Python is forced to UTF-8 so Unicode benchmark output does not fail under cp1255 Hebrew Windows terminals.",
            "Peak RSS is sampled for the benchmark process tree, not isolated per encoder.",
            "On Windows/WDDM, per-process VRAM from nvidia-smi may be unavailable; total GPU memory delta is also measured.",
            "Total GPU memory delta can include activity from unrelated GPU processes; keep the machine reasonably idle for cleaner evidence.",
            "Wall time includes model setup/loading performed by the benchmark process.",
            "Use the benchmark report's per-encoder medians for encoder execution timing.",
        ],
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.samples_csv:
        csv_path = Path(args.samples_csv)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "elapsed_s",
                    "rss_mb",
                    "nvidia_process_vram_mb",
                    "nvidia_total_gpu_used_mb",
                ],
            )
            writer.writeheader()
            writer.writerows(samples)

    print("\n=== Phase 11 resource benchmark summary ===")
    print(f"Device: {args.device}")
    print(f"Return code: {return_code}")
    print(f"Wall time: {wall_s:.3f}s")
    print(f"Peak process-tree RSS: {peak_rss_mb:.1f} MB")

    if args.device == "cuda":
        print(f"NVIDIA baseline total used: {gpu_baseline_mb} MB")
        print(f"NVIDIA peak total used: {peak_total_gpu_used_mb} MB")
        print(f"NVIDIA peak delta: {gpu_delta_mb} MB")
        if peak_process_vram_mb is None:
            print("NVIDIA per-process VRAM: unavailable on this Windows/WDDM path")
        else:
            print(f"NVIDIA peak process VRAM: {peak_process_vram_mb:.1f} MB")
    else:
        print("NVIDIA VRAM: not applicable")

    print(f"Report: {out.resolve()}")
    if args.samples_csv:
        print(f"Samples: {Path(args.samples_csv).resolve()}")

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
