from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.brain_v2.features.pixel_stats import (  # noqa: E402
    compute_pixel_statistics,
    pixel_statistics_feature_vector,
)
from app.brain_v2.preprocessing.raw_decode import decode_raw  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ProGrapher Phase 11 real RAW decode/statistics probe"
    )
    parser.add_argument("--raw", required=True)
    parser.add_argument(
        "--output",
        default=str(
            BACKEND_ROOT.parent
            / "docs"
            / "runtime"
            / "phase11_raw_probe.json"
        ),
    )
    args = parser.parse_args()

    try:
        frame = decode_raw(args.raw)
    except RuntimeError as exc:
        print(f"❌ {exc}")
        print()
        print("התקנה:")
        print(
            r'.\.venv\Scripts\python.exe -m pip install -r requirements-phase11.txt'
        )
        return 2
    except (OSError, ValueError) as exc:
        print(f"❌ RAW probe נכשל: {exc}")
        return 3

    stats = compute_pixel_statistics(frame)
    vector = pixel_statistics_feature_vector(stats)

    payload = {
        "schema": "prographer.phase11.raw-probe.v1",
        "source_path": frame.source_path,
        "source_sha256": frame.source_sha256,
        "decode": frame.metadata.to_dict(),
        "statistics": stats.to_dict(),
        "feature_vector": {
            "version": vector.version,
            "feature_names": list(vector.feature_names),
            "values": list(vector.values),
        },
        "important_note": (
            "This probe uses decoded RAW pixels only. "
            "No embedded JPEG preview is used."
        ),
    }

    destination = Path(args.output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print("✅ Phase 11 RAW probe PASS")
    print(f"RAW engine: {frame.metadata.raw_engine}")
    print(f"rawpy: {frame.metadata.raw_engine_version}")
    print(f"NumPy: {frame.metadata.numpy_version}")
    print(
        f"Decoded: {frame.metadata.width}x{frame.metadata.height} "
        f"16-bit -> float32 linear sRGB"
    )
    print(f"Camera WB: {frame.metadata.camera_wb}")
    print(f"Luminance mean: {stats.luminance_mean:.6f}")
    print(f"Luminance p05: {stats.luminance_p05:.6f}")
    print(f"Luminance p50: {stats.luminance_p50:.6f}")
    print(f"Luminance p95: {stats.luminance_p95:.6f}")
    print(f"Highlight clip: {stats.highlight_clip_fraction:.6%}")
    print(f"Shadow clip: {stats.shadow_clip_fraction:.6%}")
    print(f"Features: {len(vector.values)}")
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
