"""RAW-CAT-01F.02A — bounded SOURCE-ONLY RAW luminance/color smoke probe.

Research diagnostics, NOT a scene classifier, Adobe color match or a Brain.
Photo names, source paths, hashes and individual measurements never leave memory.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import numpy as np

from app.brain_v2.preprocessing.raw_decode import (
    RAW_PREPROCESSING_VERSION, decode_raw, deterministic_sample,
)
from app.photographer.raw_catalog_intake import _write_atomic


def describe_linear_rgb(rgb: np.ndarray) -> dict[str, float]:
    """Bounded deterministic sampling in fixed linear-sRGB camera-WB pipeline.

    Sensor highlight clipping cannot be inferred from post-demosaic RGB clipping;
    this is a decoded-RGB proxy, not a semantic scene diagnosis.
    """
    small = deterministic_sample(rgb, max_pixels=250_000)
    if small.ndim != 3 or small.shape[2] != 3 or not np.all(np.isfinite(small)):
        raise ValueError("invalid decoded RGB sample")
    if small.size == 0 or np.min(small) < 0 or np.max(small) > 1:
        raise ValueError("decoded RGB outside 0..1")
    pixels = small.astype(np.float64, copy=False)
    lum = (0.2126 * pixels[:, :, 0] +
           0.7152 * pixels[:, :, 1] +
           0.0722 * pixels[:, :, 2]).reshape(-1)
    channel_mean = pixels.reshape(-1, 3).mean(axis=0)
    return {
        "luminance_p05_linear": float(np.percentile(lum, 5)),
        "luminance_p50_linear": float(np.percentile(lum, 50)),
        "luminance_p95_linear": float(np.percentile(lum, 95)),
        "fraction_luminance_below_0_03": float(np.mean(lum < 0.03)),
        "fraction_decoded_rgb_any_channel_above_0_985": float(
            np.mean(np.any(pixels >= 0.985, axis=2))
        ),
        "linear_mean_r": float(channel_mean[0]),
        "linear_mean_g": float(channel_mean[1]),
        "linear_mean_b": float(channel_mean[2]),
    }


def choose_sample(root: Path, n: int) -> list[Path]:
    """Evenly spread across SORTED FILENAMES, not actual event/scene classes."""
    if not 1 <= n <= 12:
        raise ValueError("--max-files must be 1..12 for bounded manual research")
    files = sorted(p for p in root.rglob("*")
                   if p.is_file() and not p.is_symlink()
                   and not p.name.startswith("._") and p.suffix.lower() == ".cr3")
    if not files:
        raise ValueError("No .CR3 sources found")
    k = min(n, len(files))
    return [files[0]] if k == 1 else [
        files[(i * (len(files) - 1)) // (k - 1)] for i in range(k)
    ]


def probe(raw_dir: str | Path, max_files: int) -> dict:
    root = Path(raw_dir).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("raw-dir must be a directory")
    sample = choose_sample(root, max_files)
    measured: list[dict[str, float]] = []
    failures: Counter[str] = Counter()
    engine_versions: Counter[str] = Counter()
    for raw_path in sample:
        try:
            frame = decode_raw(raw_path)
            measurements = describe_linear_rgb(frame.rgb_linear)
            measured.append(measurements)
            engine_versions[frame.metadata.raw_engine_version] += 1
            del frame
        except (OSError, ValueError, RuntimeError, MemoryError) as exc:
            # Deliberately do NOT include exception messages: may contain filenames.
            failures[type(exc).__name__] += 1
    keys = tuple(measured[0]) if measured else ()
    summary = {key: {
        "min": min(row[key] for row in measured),
        "median": median(row[key] for row in measured),
        "max": max(row[key] for row in measured),
    } for key in keys}
    return {
        "schema": "prographer.raw_visual_context_source_probe.v0",
        "status": "SOURCE_ONLY_ENGINEERING_RESEARCH_NOT_SCENE_OR_BRAIN",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "privacy": "AGGREGATE ONLY: filenames, paths, captured dates, hashes, images and per-photo features omitted",
        "source": "Original .CR3 files only; no Lightroom previews, .lrcat Develop targets, XMP or edited JPEG inputs",
        "raw_pipeline": RAW_PREPROCESSING_VERSION,
        "decode": "rawpy/LibRaw fixed linear-sRGB, camera white balance; NOT colorimetric validation or Adobe parity",
        "selection": "Even spacing across lexical RAW filenames, NOT validated scene/event stratification",
        "attempted": len(sample),
        "decoded": len(measured),
        "failed": dict(sorted(failures.items())),
        "engine_versions": dict(sorted(engine_versions.items())),
        "feature_aggregates": summary,
        "training_ready": False,
        "next": "Confirm photographer event/finality/permission, independent scene annotation and locked event splits before prediction experiment",
    }


def main() -> int:
    cli = argparse.ArgumentParser(description="Bounded read-only original-CR3 visual diagnostics (not AI)")
    cli.add_argument("--raw-dir", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    cli.add_argument("--max-files", type=int, default=6)
    cli.add_argument("--consent-acknowledged", action="store_true",
                     help="Explicitly confirm the photographer has approved this private RAW pixel analysis")
    args = cli.parse_args()
    if not args.consent_acknowledged:
        cli.error("Do not decode photographer images without explicit research permission; add --consent-acknowledged only after approval")
    try:
        root = args.raw_dir.expanduser().resolve(strict=True)
        report_path = args.report.expanduser().resolve()
        if report_path.is_relative_to(root):
            raise ValueError("report must be outside the source RAW folder")
        report = probe(root, args.max_files)
        _write_atomic(report_path, report)
    except (OSError, ValueError, MemoryError) as exc:
        cli.exit(2, f"RAW CONTEXT PROBE FAILED (source unchanged): {exc}\n")
    print("Aggregate report:", report_path)
    print("CR3 attempted:", report["attempted"])
    print("Decoded successfully:", report["decoded"])
    print("Failed:", sum(report["failed"].values()))
    print("Scene classification and Brain training: NOT PERFORMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
