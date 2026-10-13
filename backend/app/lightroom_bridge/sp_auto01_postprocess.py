"""SP-AUTO-01: automatically analyze the JPEG returned by a VERIFIED bridge job.

Research only. Requires one successful, private disposable-catalog Lightroom
bridge job. Reads only neutral JPEG pixels for source features and CLIP; the
original photographer Develop target is never passed to the visual analyzer.
Never changes Lightroom, the catalog, JPEG, master recipe or training status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from app.lightroom_bridge import sp_auto01
from app.photographer.smart_preview_analysis import analyze_neutral_jpeg

SCHEMA = "prographer.spauto01.verified_bridge_analysis.v1"
OUTPUT_NAME = "SP_01_AUTO_ANALYSIS"
PRIVATE_REPORT = "AUTO_ANALYSIS_PRIVATE.json"
AGGREGATE_REPORT = "AUTO_ANALYSIS_AGGREGATE.json"


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def analyze_completed_job(*, predictor: Any | None = None,
                          root_override: Path | None = None) -> dict[str, Any]:
    """Start only after the unchanged SP-AUTO-01 result verifier says PASS."""
    passed, _ = sp_auto01.verify(root_override=root_override)
    if not passed:
        raise ValueError("auto-export job is not verified")
    _, _, _, work = sp_auto01._context(root_override)
    job = sp_auto01._fields(work / "job.txt")
    state = sp_auto01._fields(work / "result.txt")

    if state["status"] != "ok" or job["job_id"] != state["job_id"]:
        raise ValueError("job identity mismatch")
    export_dir = (work / "exports").resolve(strict=True)
    jpeg = Path(state["jpeg"])
    target = Path(state["target_snapshot"])
    if (jpeg.is_symlink() or not jpeg.is_file()
        or jpeg.resolve(strict=True).parent != export_dir):
        raise ValueError("source JPEG not in approved bridge export folder")
    if (target.is_symlink() or not target.is_file()
        or target.resolve(strict=True) != (work / "master_target_PRIVATE.txt").resolve()):
        raise ValueError("private master target missing or redirected")

    out_dir = work / OUTPUT_NAME
    if out_dir.is_symlink() or out_dir.exists():
        raise FileExistsError("analysis already exists; no retry/overwrite")

    # Independent hashes prove we did not alter either file while analyzing.
    source_before, target_before = _digest(jpeg), _digest(target)
    analysis = analyze_neutral_jpeg(jpeg, predictor=predictor)
    if (source_before != _digest(jpeg) or target_before != _digest(target)
        or analysis["source_sha256_PRIVATE"] != source_before):
        raise ValueError("input or photographer target changed during analysis")
    # Intentionally retain the entire copied master target separately.
    # Do NOT insert its content in a source feature vector or prompt.
    private_report = {
        "schema": SCHEMA,
        "status": "UNAPPROVED_RESEARCH_ONLY",
        "bridge_job_id_PRIVATE": job["job_id"],
        "catalog_master_uuid_PRIVATE": state["master_uuid"],
        "catalog_virtual_copy_uuid_PRIVATE": state["copy_uuid"],
        "photographer_target_path_PRIVATE": str(target.resolve()),
        "photographer_target_sha256_PRIVATE": target_before,
        "source_analysis_ONLY_NEUTRAL_JPEG": {
            **analysis,
            "source_kind": "LIGHTROOM_SDK_AUTO_EXPORTED_SMART_PREVIEW_NEUTRAL_JPEG_UNVERIFIED",
        },
        "visual_model_received_master_develop_target": False,
        "independent_neutrality_leakage_gate_passed": False,
        "training_ready": False,
    }
    aggregate = {
        "schema": SCHEMA,
        "status": "BRIDGE_PASS_VISUAL_ANALYSIS_COMPLETED",
        "analyzed": 1,
        "scene_status": analysis["scene"]["status"],
        "scene_abstained": bool(analysis["scene"]["abstained"]),
        "bridge_verified": True,
        "training_ready": 0,
        "disclaimer": (
            "Smart Preview sRGB/JPEG pixels, not source RAW-linear measurements. "
            "Neutrality independence and source-target leakage gates remain open."
        ),
    }
    out_dir.mkdir()
    # Fail closed on any existing artifact; no reuse or overwrite of prior run.
    with (out_dir / PRIVATE_REPORT).open("x", encoding="utf-8") as handle:
        json.dump(private_report, handle, indent=2, ensure_ascii=False)
    with (out_dir / AGGREGATE_REPORT).open("x", encoding="utf-8") as handle:
        json.dump(aggregate, handle, indent=2, ensure_ascii=False)
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze one VERIFIED Lightroom bridge JPEG automatically, locally"
    )
    parser.add_argument("--research-consent", action="store_true")
    parser.add_argument("--run-scene-ai", action="store_true",
                        help="Use already-cached CLIP weights without downloading anything")
    args = parser.parse_args()
    if not args.research_consent:
        parser.error("photographer's explicit local research consent is required")
    try:
        predictor = None
        if args.run_scene_ai:
            from app.photographer.smart_preview_ranked_scene import RankedSmartPreviewClip
            predictor = RankedSmartPreviewClip(allow_model_download=False)
        result = analyze_completed_job(predictor=predictor)
    except (FileExistsError, ValueError, OSError, RuntimeError, MemoryError) as exc:
        parser.exit(2, f"SP-AUTO-01 ANALYSIS STOPPED: {type(exc).__name__}\n")
    print("SP-AUTO-01 verified Lightroom JPEG analyzed:", result["analyzed"])
    print("Visual inference status:", result["scene_status"])
    print("Training ready: 0; master target was not sent to vision model")
    print("Analysis stays in the private bridge workdir (do not upload private report).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
