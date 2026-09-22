from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def _numeric_array(value: np.ndarray) -> np.ndarray | None:
    arr = np.asarray(value)
    if arr.dtype.kind not in "biufc":
        return None
    return arr.astype(np.float64, copy=False)


def _cosine(a: np.ndarray, b: np.ndarray) -> float | None:
    af = a.reshape(-1)
    bf = b.reshape(-1)
    if af.size == 0 or bf.size == 0:
        return None
    na = float(np.linalg.norm(af))
    nb = float(np.linalg.norm(bf))
    if na == 0.0 and nb == 0.0:
        return 1.0
    if na == 0.0 or nb == 0.0:
        return None
    return float(np.dot(af, bf) / (na * nb))


def compare_npz(cpu_path: Path, cuda_path: Path) -> dict[str, Any]:
    with np.load(cpu_path, allow_pickle=False) as cpu, np.load(cuda_path, allow_pickle=False) as cuda:
        cpu_keys = set(cpu.files)
        cuda_keys = set(cuda.files)
        common = sorted(cpu_keys & cuda_keys)

        report: dict[str, Any] = {
            "cpu_file": str(cpu_path.resolve()),
            "cuda_file": str(cuda_path.resolve()),
            "cpu_keys": sorted(cpu_keys),
            "cuda_keys": sorted(cuda_keys),
            "missing_from_cpu": sorted(cuda_keys - cpu_keys),
            "missing_from_cuda": sorted(cpu_keys - cuda_keys),
            "comparisons": {},
        }

        for key in common:
            a_raw = cpu[key]
            b_raw = cuda[key]

            entry: dict[str, Any] = {
                "cpu_shape": list(a_raw.shape),
                "cuda_shape": list(b_raw.shape),
                "cpu_dtype": str(a_raw.dtype),
                "cuda_dtype": str(b_raw.dtype),
            }

            if a_raw.shape != b_raw.shape:
                entry["status"] = "shape_mismatch"
                report["comparisons"][key] = entry
                continue

            a = _numeric_array(a_raw)
            b = _numeric_array(b_raw)
            if a is None or b is None:
                entry["status"] = "non_numeric_skipped"
                report["comparisons"][key] = entry
                continue

            finite = bool(np.isfinite(a).all() and np.isfinite(b).all())
            diff = a - b
            abs_diff = np.abs(diff)

            max_abs = float(abs_diff.max()) if abs_diff.size else 0.0
            mean_abs = float(abs_diff.mean()) if abs_diff.size else 0.0
            rmse = float(np.sqrt(np.mean(diff * diff))) if diff.size else 0.0
            l2_diff = float(np.linalg.norm(diff.reshape(-1)))
            l2_cpu = float(np.linalg.norm(a.reshape(-1)))
            relative_l2 = None if l2_cpu == 0.0 else float(l2_diff / l2_cpu)
            cosine = _cosine(a, b)

            entry.update(
                {
                    "status": "compared",
                    "finite": finite,
                    "element_count": int(a.size),
                    "max_abs_diff": max_abs,
                    "mean_abs_diff": mean_abs,
                    "rmse": rmse,
                    "l2_diff": l2_diff,
                    "relative_l2_vs_cpu": relative_l2,
                    "cosine_similarity": cosine,
                    "allclose_1e-5_1e-6": bool(np.allclose(a, b, rtol=1e-5, atol=1e-6)),
                    "allclose_1e-4_1e-5": bool(np.allclose(a, b, rtol=1e-4, atol=1e-5)),
                }
            )
            report["comparisons"][key] = entry

        report["summary"] = {
            "same_key_set": cpu_keys == cuda_keys,
            "compared_key_count": sum(
                1 for v in report["comparisons"].values() if v.get("status") == "compared"
            ),
            "shape_mismatch_count": sum(
                1 for v in report["comparisons"].values() if v.get("status") == "shape_mismatch"
            ),
            "non_numeric_skipped_count": sum(
                1 for v in report["comparisons"].values() if v.get("status") == "non_numeric_skipped"
            ),
        }
        return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare Phase 11 CPU and CUDA encoder NPZ outputs numerically."
    )
    parser.add_argument("--cpu", required=True, type=Path)
    parser.add_argument("--cuda", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = compare_npz(args.cpu, args.cuda)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)

    print("\n=== Phase 11 CPU ↔ CUDA vector comparison ===")
    print(f"Same key set: {report['summary']['same_key_set']}")
    print(f"Compared keys: {report['summary']['compared_key_count']}")
    print(f"Shape mismatches: {report['summary']['shape_mismatch_count']}")
    print()

    for key, entry in report["comparisons"].items():
        print(f"[{key}]")
        print(f"  status: {entry['status']}")
        if entry["status"] == "compared":
            print(f"  shape: {entry['cpu_shape']}")
            print(f"  cosine_similarity: {entry['cosine_similarity']}")
            print(f"  max_abs_diff: {entry['max_abs_diff']}")
            print(f"  mean_abs_diff: {entry['mean_abs_diff']}")
            print(f"  rmse: {entry['rmse']}")
            print(f"  relative_l2_vs_cpu: {entry['relative_l2_vs_cpu']}")
            print(f"  allclose(1e-5,1e-6): {entry['allclose_1e-5_1e-6']}")
            print(f"  allclose(1e-4,1e-5): {entry['allclose_1e-4_1e-5']}")
        print()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Report: {args.output.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
