"""SP-AUTO-01: one-photo autonomous neutral-Smart-Preview research bridge.

Two-sided local IPC with an Adobe Lightroom Classic SDK research plug-in.
*Only* the disposable SP_01_AUTO_E2E_01 catalog is authorized.
Does not modify source files/catalogs itself, train, or open Lightroom.
Research catalog IS mutated by the Lua worker to create one temporary VC.
Prepare only once per clean work folder; never retries a partial job.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4

RESEARCH_NAME = "ProGrapher_Research_Private"
CATALOG_PARENT = Path("SP_01_Catalog_Test") / "SP_01_AUTO_E2E_01"
CATALOG_NAME = "SP_01_AUTO_E2E_01.lrcat"
PREVIEW_NAME = "SP_01_AUTO_E2E_01 Smart Previews.lrdata"
WORK_NAME = "SP_01_AUTO_BRIDGE"
VERSION = "spauto01-1"
FORMAT = re.compile(r"[0-9a-f]{32}\Z")
FIELDS = ("version", "job_id", "catalog_path", "export_dir",
          "operation", "selection_policy", "neutral_policy")
RESULT_BASE = ("status", "job_id")
SUCCESS_FIELDS = ("status", "job_id", "jpeg", "bytes", "master_uuid",
                  "copy_uuid", "raw_offline", "smart_preview",
                  "master_develop_unchanged", "neutral_exposure",
                  "neutral_cropped", "target_snapshot")
NEUTRAL_POLICY = "lightroom-reset-defaults-v1-UNVERIFIED"
OPERATION = "EXTRACT_NEUTRAL_SMART_PREVIEW"
SELECTION = "EXACTLY_ONE_MASTER_IN_DISPOSABLE_CATALOG"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fields(path: Path) -> dict[str, str]:
    if path.stat().st_size > 8192:
        raise ValueError("oversized protocol file")
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.startswith("#"):
            continue
        k, delim, v = line.partition("=")
        if not delim or not re.fullmatch("[a-z][a-z0-9_]*", k) or not v or k in result:
            raise ValueError("malformed bridge protocol")
        result[k] = v
    return result


def _write_once(path: Path, fields: dict[str, str]) -> None:
    for k, v in fields.items():
        if not re.fullmatch("[a-z][a-z0-9_]*", k) or not v or "\r" in v or "\n" in v:
            raise ValueError("unsafe protocol field")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for key, val in fields.items():
            stream.write(f"{key}={val}\n")


def _context(root_override: Path | None = None) -> tuple[Path, Path, Path, Path]:
    root = (root_override or Path.home() / "Documents" / RESEARCH_NAME)
    if root.is_symlink():
        raise ValueError("research root must not be redirected")
    root = root.resolve(strict=True)
    if not root.is_dir() or root.name != RESEARCH_NAME:
        raise ValueError("research root must be private local research folder")
    parent = root
    for part in CATALOG_PARENT.parts:
        parent = parent / part
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError("missing or redirected test catalog folder")
    catalog = parent / CATALOG_NAME
    smart = parent / PREVIEW_NAME
    if catalog.is_symlink() or not catalog.is_file() or catalog.stat().st_size < 1024:
        raise ValueError("missing disposable Lightroom research catalog")
    if smart.is_symlink() or not smart.is_dir():
        raise ValueError("missing Smart Preview research store")
    workdir = parent / WORK_NAME
    if workdir.is_symlink():
        raise ValueError("redirected bridge workdir")
    return root, catalog, smart, workdir


def prepare(*, root_override: Path | None = None) -> Path:
    _, catalog, _, workdir = _context(root_override)
    # Workdir must be NEW. A previous 'running' or failed job is evidence,
    # never silently reset / retried; use a new isolated research catalog.
    if workdir.exists():
        raise FileExistsError("SP-AUTO-01 workdir already exists; inspect previous job")
    workdir.mkdir()
    output = workdir / "exports"
    output.mkdir()
    job_id = uuid4().hex
    # Publish PREPARED status before job: background plug-in sees a complete job.
    _write_once(workdir / "result.txt", {"status": "prepared", "job_id": job_id})
    _write_once(workdir / "job.txt", {
        "version": VERSION, "job_id": job_id,
        "catalog_path": str(catalog), "export_dir": str(output),
        "operation": OPERATION, "selection_policy": SELECTION,
        "neutral_policy": NEUTRAL_POLICY,
    })
    return workdir / "job.txt"


def verify(*, root_override: Path | None = None) -> tuple[bool, str]:
    _, catalog, _, workdir = _context(root_override)
    try:
        job = _fields(workdir / "job.txt")
        result = _fields(workdir / "result.txt")
    except (FileNotFoundError, ValueError, OSError):
        return False, "NOT_READY_OR_MALFORMED"
    if (set(job) != set(FIELDS) or job["version"] != VERSION
        or not FORMAT.fullmatch(job["job_id"])
        or Path(job["catalog_path"]) != catalog
        or job["operation"] != OPERATION
        or job["selection_policy"] != SELECTION
        or job["neutral_policy"] != NEUTRAL_POLICY
        or Path(job["export_dir"]) != workdir / "exports"):
        return False, "INVALID_RESEARCH_JOB"
    if result.get("job_id") != job["job_id"]:
        return False, "STALE_OR_MISMATCHED_JOB"
    status = result.get("status")
    if status != "ok":
        return False, "NOT_COMPLETE_" + str(status or "UNKNOWN").upper()
    if set(result) != set(SUCCESS_FIELDS):
        return False, "INCOMPLETE_OR_UNEXPECTED_RESULT"
    if result["raw_offline"] != "true" or result["smart_preview"] != "true" or (
        result["master_develop_unchanged"] != "true"
    ) or result["neutral_cropped"] != "false":
        return False, "SOURCE_OR_TARGET_PROTECTION_FAILED"
    try:
        exposure = float(result["neutral_exposure"])
        if not abs(exposure) < 0.01:
            return False, "RESET_BASELINE_NOT_VERIFIED"
        jpeg = Path(result["jpeg"])
        safe_exports = workdir / "exports"
        if (jpeg.is_symlink() or not jpeg.is_file()
            or jpeg.resolve(strict=True).parent != safe_exports.resolve(strict=True)
            or jpeg.suffix.lower() not in (".jpg", ".jpeg")):
            return False, "JPEG_OUTSIDE_PRIVATE_OUTPUT"
        if int(result["bytes"]) != jpeg.stat().st_size or jpeg.stat().st_size < 1024:
            return False, "INVALID_JPEG_SIZE"
        target = Path(result["target_snapshot"])
        if (target.is_symlink() or target != workdir / "master_target_PRIVATE.txt"
            or not target.is_file() or not 200 <= target.stat().st_size <= 16 * 1024 * 1024):
            return False, "INVALID_PRIVATE_TARGET"
        if not result["master_uuid"] or result["master_uuid"] == result["copy_uuid"]:
            return False, "INVALID_PHOTO_IDENTITY"
        target_text = target.read_text(encoding="utf-8")
        if (f"job_id={job['job_id']}\n" not in target_text
            or f"master_uuid={result['master_uuid']}\n" not in target_text
            or "full_develop_serialized_PRIVATE=" not in target_text):
            return False, "MASTER_TARGET_SNAPSHOT_MISMATCH"
        # Force image decoding rather than trusting path and extension.
        from PIL import Image
        with Image.open(jpeg) as img:
            if img.format != "JPEG" or img.width < 32 or img.height < 32:
                return False, "INVALID_JPEG"
            img.verify()
        _ = _sha256(jpeg)
    except (OSError, ValueError, OverflowError):
        return False, "CORRUPT_OR_UNAVAILABLE_OUTPUT"
    return True, "PASS_ONE_PHOTO_DISPOSABLE_CATALOG_ONLY_NO_TRAINING"


def main() -> int:
    p = argparse.ArgumentParser(description="SP-AUTO-01 disposable catalog research bridge")
    p.add_argument("action", choices=["prepare", "verify"])
    p.add_argument("--research-consent", action="store_true",
                   help="Confirm photographer permits local research on disposable catalog")
    args = p.parse_args()
    if not args.research_consent:
        p.error("explicit local research consent is required")
    try:
        if args.action == "prepare":
            prepare()
            print("SP-AUTO-01 job PREPARED for background Lightroom plug-in.")
            print("Open only SP_01_AUTO_E2E_01.lrcat and wait for the plug-in.")
            print("No automatic catalog switching, no edits to production catalogs.")
            return 0
        ok, msg = verify()
        print("SP-AUTO-01 verification:", msg)
        print("Training-ready: 0 (neutral leakage gate remains open)")
        return 0 if ok else 2
    except (FileExistsError, ValueError, OSError) as exc:
        p.exit(2, "SP-AUTO-01 STOPPED: " + type(exc).__name__ + " (no retry)\n")


if __name__ == "__main__":
    raise SystemExit(main())
