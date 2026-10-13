"""SP-AUTO-03: one-shot, VC-only controlled Develop anti-leakage research.

Never edit the master, original RAW, prior research catalogs, or any user
catalog. Only one strict disposable SP_01_AUTO_LEAK_01.lrcat is authorized.

Claims are LIMITED: two edited virtual-copy histories converge on the exact
same full Lightroom Develop readback and decoded RGB pixels after reset.
That does not establish that historical Smart Preview pixels were RAW-linear,
bake-free, or suitable for photographer model training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from app.lightroom_bridge import sp_auto01 as earlier
from app.lightroom_bridge.sp_auto02_one_command import wait_for_bridge
from app.photographer.smart_preview_repeatability import compare_decoded_jpegs

RESEARCH_NAME = "ProGrapher_Research_Private"
CATALOG_DIR = Path("SP_01_Catalog_Test") / "SP_01_AUTO_LEAK_01"
CATALOG_FILE = "SP_01_AUTO_LEAK_01.lrcat"
SMART_DIR = "SP_01_AUTO_LEAK_01 Smart Previews.lrdata"
WORK_DIR = "SP_03_BRIDGE"
VERSION = "spauto03-1"
OPERATION = "COUNTERFACTUAL_VC_RESET"
NEUTRAL_POLICY = "lightroom-reset-defaults-v1-UNVERIFIED"
SELECTION = "ONE_OFFLINE_MASTER_ZERO_COPIES"
AGGREGATE_NAME = "SP03_AGGREGATE.json"

FIELDS = ("version", "job_id", "catalog_path", "export_dir", "operation",
          "neutral_policy", "selection_policy")
SUCCESS_FIELDS = (
    "status", "job_id", "jpeg_a", "jpeg_b", "jpeg_perturbed", "master_uuid", "copy_a_uuid",
    "copy_b_uuid", "target_fingerprint_unchanged",
    "pre_reset_variants_distinct", "post_reset_full_develop_equal",
    "post_reset_exposure_a", "post_reset_exposure_b",
    "post_reset_uncropped_a", "post_reset_uncropped_b",
    "source_raw_offline", "smart_preview_present",
)

def _context(root_override: Path | None = None) -> tuple[Path, Path, Path, Path]:
    root = root_override or Path.home() / "Documents" / RESEARCH_NAME
    if root.is_symlink():
        raise ValueError("redirected research root")
    root = root.resolve(strict=True)
    if root.name != RESEARCH_NAME:
        raise ValueError("not research root")
    folder = root
    for item in CATALOG_DIR.parts:
        folder /= item
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("research catalog directory invalid")
    catalog = folder / CATALOG_FILE
    smart = folder / SMART_DIR
    if (catalog.is_symlink() or not catalog.is_file()
        or catalog.stat().st_size < 1024
        or smart.is_symlink() or not smart.is_dir()):
        raise ValueError("catalog or Smart Previews unavailable")
    work = folder / WORK_DIR
    if work.is_symlink():
        raise ValueError("redirected output folder")
    return root, catalog, smart, work


def prepare(*, root_override: Path | None = None) -> Path:
    root, catalog, smart, work = _context(root_override)
    if work.exists():
        raise FileExistsError("one-shot research job already exists: never replay")
    work.mkdir()
    (work / "exports").mkdir()
    (work / "exports" / "A").mkdir()
    (work / "exports" / "B").mkdir()
    (work / "exports" / "P").mkdir()
    from uuid import uuid4
    job_id = uuid4().hex
    # Both protocols atomically created ONCE; worker cannot claim partial job.
    earlier._write_once(work / "result.txt", {
        "status": "prepared", "job_id": job_id
    })
    earlier._write_once(work / "job.txt", {
        "version": VERSION, "job_id": job_id, "catalog_path": str(catalog),
        "export_dir": str(work / "exports"), "operation": OPERATION,
        "neutral_policy": NEUTRAL_POLICY, "selection_policy": SELECTION,
    })
    return work / "job.txt"


def _is_valid_jpeg(path: Path, directory: Path) -> bool:
    if (directory.is_symlink() or directory.parent.is_symlink()
        or path.is_symlink() or not path.is_file()
        or path.suffix.casefold() not in {".jpg", ".jpeg"}
        or path.stat().st_size < 1024
        or path.resolve(strict=True).parent != directory.resolve(strict=True)):
        return False
    from PIL import Image
    with Image.open(path) as img:
        if img.format != "JPEG" or min(img.size) < 32:
            return False
        img.verify()
    return True


def verify(*, root_override: Path | None = None) -> tuple[bool, str, dict | None]:
    _, catalog, _smart, work = _context(root_override)
    try:
        job = earlier._fields(work / "job.txt")
        result = earlier._fields(work / "result.txt")
    except (OSError, ValueError):
        return False, "INVALID_JOB_OR_STATUS", None
    if (set(job) != set(FIELDS) or job["version"] != VERSION
        or not earlier.FORMAT.fullmatch(job["job_id"])
        or Path(job["catalog_path"]) != catalog
        or Path(job["export_dir"]) != work / "exports"
        or job["operation"] != OPERATION
        or job["neutral_policy"] != NEUTRAL_POLICY
        or job["selection_policy"] != SELECTION
        or result.get("job_id") != job["job_id"]):
        return False, "INVALID_OR_REDIRECTED_JOB", None
    if result.get("status") != "ok":
        return False, "NOT_COMPLETE_" + result.get("status", "UNKNOWN").upper(), None
    if set(result) != set(SUCCESS_FIELDS):
        return False, "UNEXPECTED_SUCCESS_FIELDS", None
    guards = (
        "target_fingerprint_unchanged", "pre_reset_variants_distinct",
        "post_reset_full_develop_equal", "post_reset_uncropped_a",
        "post_reset_uncropped_b", "source_raw_offline",
        "smart_preview_present",
    )
    if any(result[k] != "true" for k in guards):
        return False, "SDK_PROOF_GUARD_FAILED", None
    ids = {result["master_uuid"], result["copy_a_uuid"], result["copy_b_uuid"]}
    if len(ids) != 3 or any(not identity for identity in ids):
        return False, "NON_UNIQUE_COPY_IDENTITIES", None
    try:
        a = float(result["post_reset_exposure_a"])
        b = float(result["post_reset_exposure_b"])
        if not (math.isfinite(a) and math.isfinite(b) and
                abs(a) <= 0.01 and abs(b) <= 0.01):
            return False, "DEVELOP_NEUTRAL_EXPOSURE_FAILED", None
        jpeg_a = Path(result["jpeg_a"])
        jpeg_b = Path(result["jpeg_b"])
        jpeg_perturbed = Path(result["jpeg_perturbed"])
        if not (_is_valid_jpeg(jpeg_a, work / "exports" / "A")
                and _is_valid_jpeg(jpeg_b, work / "exports" / "B")
                and _is_valid_jpeg(jpeg_perturbed, work / "exports" / "P")):
            return False, "INVALID_OR_REDIRECTED_JPEG", None
        pixels = compare_decoded_jpegs(jpeg_a, jpeg_b)
        intervention = compare_decoded_jpegs(jpeg_perturbed, jpeg_a)
    except (OSError, ValueError, OverflowError, MemoryError):
        return False, "RENDER_VALIDATION_FAILED", None

    safe = {
        "schema": "prographer.spauto03.counterfactual.v1",
        "status": "COUNTERFACTUAL_RESEARCH_COMPLETED",
        "two_distinct_pre_reset_vc_states_confirmed": True,
        "full_post_reset_develop_settings_equal": True,
        "source_master_develop_unchanged": True,
        "original_raw_offline": True,
        "smart_preview_present": True,
        "two_unique_vc_jpegs": True,
        "pre_reset_perturbation_rendered": True,
        "perturbed_pixels_differ_from_reset_baseline": (
            not intervention["pixel_equal"] if intervention["dimensions_match"] else False
        ),
        "counterfactual_perturbation_mean_absolute_rgb_difference_8bit": (
            intervention["mean_absolute_rgb_difference_8bit"]
        ),
        "dimensions_match": pixels["dimensions_match"],
        "all_decoded_rgb_pixels_equal": pixels["pixel_equal"],
        "mean_absolute_rgb_difference_8bit": pixels["mean_absolute_rgb_difference_8bit"],
        "max_absolute_rgb_difference_8bit": pixels["max_absolute_rgb_difference_8bit"],
        "byte_hashes_equal": pixels["byte_hashes_match"],
        "counterfactual_vc_reset_invariance_candidate": bool(pixels["pixel_equal"]),
        "historical_smart_preview_bake_free_proven": False,
        "all_custom_lightroom_defaults_proven_safe": False,
        "training_ready": False,
    }
    if not intervention["dimensions_match"] or intervention["pixel_equal"]:
        return False, "PERTURBATION_DID_NOT_CHANGE_RENDER", safe
    if not pixels["dimensions_match"] or not pixels["pixel_equal"]:
        return False, "COUNTERFACTUAL_RENDER_MISMATCH", safe
    return True, "PASS_VC_ONLY_RESET_INVARIANCE_NOT_BAKE_FREE", safe


def run(*, root_override: Path | None = None, timeout_seconds: float = 180) -> dict:
    _context(root_override)
    prepare(root_override=root_override)
    _, _, _, work = _context(root_override)
    status = wait_for_bridge(work, timeout_seconds=timeout_seconds)
    if status != "ok":
        raise RuntimeError("Lightroom SDK reported an error; keep evidence and do not retry")
    ok, message, safe = verify(root_override=root_override)
    if not ok:
        raise RuntimeError("counterfactual verification failed: " + message)
    summary = work / AGGREGATE_NAME
    with summary.open("x", encoding="utf-8") as out:
        json.dump(safe, out, indent=2, ensure_ascii=False)
    return safe


def main() -> int:
    p = argparse.ArgumentParser(description="SP-AUTO-03 VC-only controlled Lightroom research")
    p.add_argument("action", choices=["run", "verify"])
    p.add_argument("--research-consent", action="store_true")
    p.add_argument("--offline-smart-preview-confirmed", action="store_true")
    args = p.parse_args()
    if not args.research_consent:
        p.error("photographer research permission required")
    if args.action == "run" and not args.offline_smart_preview_confirmed:
        p.error("visually confirm Smart Preview ONLY; original RAW offline")
    try:
        if args.action == "run":
            report = run()
            print("SP-AUTO-03 VC-only counterfactual: PASS")
            print("All decoded RGB pixels equal:", report["all_decoded_rgb_pixels_equal"])
            print("Target-baked Smart Preview independence proven: False")
            print("Training-ready: False")
        else:
            ok, msg, report = verify()
            print("SP-AUTO-03:", msg)
            if report:
                print("Decoded RGB identical:", report["all_decoded_rgb_pixels_equal"])
            return 0 if ok else 2
    except TimeoutError:
        p.exit(2, "SP-AUTO-03 TIMED OUT: job remains live/pending, never retry\n")
    except (RuntimeError, ValueError, FileExistsError, OSError) as exc:
        p.exit(2, "SP-AUTO-03 STOPPED: " + type(exc).__name__ +
               " (preserve catalog/job; do not retry)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
