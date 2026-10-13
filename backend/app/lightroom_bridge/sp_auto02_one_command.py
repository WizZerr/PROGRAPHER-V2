"""SP-AUTO-02 — single-command, one-shot private Lightroom -> AI research pipeline.

Prerequisite: Lightroom Classic is open on the unique disposable
SP_01_AUTO_E2E_01 catalog with the original CR3 OFFLINE and Smart Preview
available. Research plug-in must be active and user must close modal dialogs.
This does not open Lightroom or auto-switch catalogs.

One run: prepare ONE job -> await Adobe SDK bridge terminal status -> strict
verification -> neutral JPEG visual/CLIP analysis -> manual reference render
comparison -> JPEG encoding forensics -> anonymous summary.

Never replay a prepared, running, error, or completed job. Work folder cannot
be reused. No catalog/RAW/photographer Develop changes by Python. No training.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Callable, Any

from app.lightroom_bridge import sp_auto01
from app.lightroom_bridge import sp_auto01_postprocess as postprocess
from app.lightroom_bridge import sp_auto01_reference_compare as reference
from app.lightroom_bridge import sp_auto02_export_forensics as forensics

PIPELINE_SCHEMA = "prographer.spauto02.one_command_research.v1"
SUMMARY_FILE = "SP01_ONE_COMMAND_AGGREGATE.json"
TERMINAL = {"ok", "error"}
DEFAULT_WAIT = 180.0


def wait_for_bridge(
    workdir: Path, *,
    timeout_seconds: float = DEFAULT_WAIT,
    poll_seconds: float = 0.75,
    clock: Callable[[], float] = time.monotonic,
    pause: Callable[[float], None] = time.sleep,
) -> str:
    """Poll local job state; never silently treat pending work as a failure or retry."""
    if not 0 < timeout_seconds <= 600 or not 0 < poll_seconds <= 10:
        raise ValueError("invalid bounded research poll")
    deadline = clock() + timeout_seconds
    while clock() < deadline:
        try:
            state = sp_auto01._fields(workdir / "result.txt")
        except (OSError, ValueError):
            # Lightroom may be replacing status file when we inspect it.
            pause(poll_seconds)
            continue
        current = state.get("status")
        if current in TERMINAL:
            return current
        if current not in {"prepared", "running"}:
            raise ValueError("unexpected Lightroom bridge status")
        pause(poll_seconds)
    raise TimeoutError(
        "Lightroom job timed out; original job remains pending. DO NOT prepare a new job"
    )


def run_pipeline(*, predictor: Any, root_override: Path | None = None,
                 timeout_seconds: float = DEFAULT_WAIT) -> dict:
    # Refuse preexisting bridge folders even if a user removed all Virtual Copies.
    root, catalog, smart, work = sp_auto01._context(root_override)
    if work.exists():
        raise FileExistsError("previous job exists; no second run or overwrite")
    if not catalog.is_file() or not smart.is_dir():
        raise ValueError("missing authorized research catalog or Smart Preview")
    sp_auto01.prepare(root_override=root_override)
    status = wait_for_bridge(work, timeout_seconds=timeout_seconds)
    if status != "ok":
        raise RuntimeError(
            "Lightroom recorded ERROR; preserve the job, do not retry or modify catalog"
        )
    verified, verification_status = sp_auto01.verify(root_override=root_override)
    if not verified:
        raise RuntimeError("Lightroom job did not pass strict Python output verification")

    # Source-only vision model: master target file is never passed to AI.
    visual = postprocess.analyze_completed_job(
        predictor=predictor, root_override=root_override
    )
    ref = reference.compare_verified_auto_to_manual(root_override=root_override)
    forensic = forensics.run(root_override=root_override)
    summary = {
        "schema": PIPELINE_SCHEMA,
        "status": "ONE_COMMAND_PIPELINE_COMPLETED",
        "bridge_verified": True,
        "bridge_verification": verification_status,
        "neutral_jpeg_visual_analysis_completed": visual["analyzed"] == 1,
        "visual_scene_status": visual["scene_status"],
        "visual_scene_abstained": visual["scene_abstained"],
        "auto_vs_manual_dimensions_match": ref["dimensions_match"],
        "auto_vs_manual_decoded_pixels_match": ref["decoded_rgb_pixels_match"],
        "auto_vs_manual_mae_8bit": ref["mean_absolute_rgb_difference_8bit"],
        "jpeg_encoding_diagnostics_completed": forensic["diagnostic_status"] == "COMPLETED_CAUSE_NOT_PROVEN",
        "jpeg_quantization_tables_match": forensic.get("jpeg_quantization_tables_match"),
        "jpeg_chroma_subsampling_match": forensic.get("jpeg_chroma_subsampling_match"),
        "source_target_leakage_independently_proven": False,
        "original_sensor_raw_reconstructed": False,
        "photographer_target_provided_to_visual_ai": False,
        "training_ready": False,
    }
    # One write to a NEW path, inside already-checked one-use private workdir.
    out = work / SUMMARY_FILE
    with out.open("x", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ONE run: Lightroom Smart Preview auto export + local AI + pixel/encoding QC"
    )
    parser.add_argument("action", choices=["run"])
    parser.add_argument("--research-consent", action="store_true")
    parser.add_argument("--smart-preview-only-confirmed", action="store_true")
    parser.add_argument("--same-photo-manual-reference-confirmed", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_WAIT)
    args = parser.parse_args()
    if not (args.research_consent and args.smart_preview_only_confirmed
            and args.same_photo_manual_reference_confirmed):
        parser.error(
            "user permission, offline Smart Preview and same-photo reference required"
        )
    try:
        # Load cached CLIP BEFORE creating the irreversible one-shot job.
        from app.photographer.smart_preview_ranked_scene import RankedSmartPreviewClip
        predictor = RankedSmartPreviewClip(allow_model_download=False)
        print("Local CLIP ready. Preparing ONE private Lightroom bridge job.")
        print("Keep Lightroom open in authorized research catalog; close Info/modal dialogs.")
        result = run_pipeline(predictor=predictor, timeout_seconds=args.timeout_seconds)
    except TimeoutError:
        parser.exit(2, "SP-AUTO-02 WAITING/TIMEOUT: job still pending. DO NOT RETRY.\n")
    except (FileExistsError, OSError, ValueError, RuntimeError, MemoryError) as exc:
        parser.exit(
            2, "SP-AUTO-02 STOPPED: " + type(exc).__name__
            + " (research evidence preserved; do NOT retry)\n"
        )
    print("SP-AUTO-02 ONE-COMMAND PIPELINE: COMPLETE")
    print("Bridge verified:", result["bridge_verified"])
    print("Neutral JPEG analyzed:", result["neutral_jpeg_visual_analysis_completed"])
    print("Scene status:", result["visual_scene_status"])
    print("Auto/manual decoded pixel match:", result["auto_vs_manual_decoded_pixels_match"])
    print("Auto/manual mean absolute 8bit difference:", result["auto_vs_manual_mae_8bit"])
    print("JPEG forensics complete:", result["jpeg_encoding_diagnostics_completed"])
    print("Training ready: False; do not upload private image/target files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
