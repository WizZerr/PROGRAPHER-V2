"""LB-01 Lightroom Classic one-RAW research adapter (manual POC; NOT a batch service).

This is an adaptation of the user-verified Lightroom Bridge v0.2.0 experiment.
Only an isolated research catalog + an original RAW COPY are accepted.
No model training, UI automation, live catalog edits or original-XMP writes.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
from pathlib import Path
from uuid import uuid4

RESEARCH_ROOT = Path.home() / "Documents" / "ProGrapher_Research_Private"
RESEARCH_BASENAME = "ProGrapher_Research_Private"
CATALOG_RELATIVE = Path("ProGrapher_RAW_Test") / "ProGrapher_RAW_Test.lrcat"
RAW_FOLDER = "RAW_Parity_Test"
JOB_FOLDER = "BRIDGE_LB01"
PROFILE = "Adobe Standard"
FORMAT_VERSION = "lb01-1"
# Python field name : (default value, minimum, maximum, Lightroom Develop API field)
ADJUSTMENTS = {
    "exposure": (0.45, -5.0, 5.0, "Exposure2012"),
    "contrast": (12, -100, 100, "Contrast2012"),
    "highlights": (-28, -100, 100, "Highlights2012"),
    "shadows": (22, -100, 100, "Shadows2012"),
    "whites": (-8, -100, 100, "Whites2012"),
    "blacks": (-12, -100, 100, "Blacks2012"),
    "vibrance": (10, -100, 100, "Vibrance"),
    "saturation": (0, -100, 100, "Saturation"),
    "temperature": (4400, 2000, 50000, "Temperature"),
    "tint": (8, -150, 150, "Tint"),
}
FILE_KEYS = (
    "version", "job_id", "catalog_path", "raw_path", "raw_sha256",
    "export_dir", "profile", *ADJUSTMENTS.keys(),
)
RESULT_KEYS = ("status", "job_id", "profile", *ADJUSTMENTS.keys(), "jpeg", "bytes")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
ID_PATTERN = re.compile(r"[0-9a-f]{32}\Z")


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def _encode(fields: dict[str, str]) -> str:
    for key, value in fields.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key) or not value or "\n" in value or "\r" in value:
            raise ValueError("Invalid job field or newline")
    return "".join(f"{key}={value}\n" for key, value in fields.items())


def _read_fields(path: Path, *, max_bytes: int = 8192) -> dict[str, str]:
    if path.stat().st_size > max_bytes:
        raise ValueError("Oversized bridge protocol file")
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError("Malformed bridge protocol")
        key, value = line.split("=", 1)
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key) or not value or key in fields:
            raise ValueError("Duplicate/invalid bridge protocol field")
        fields[key] = value
    return fields


def _atomic_text(path: Path, content: str) -> None:
    # Atomic on the same volume; one file-based research job at a time.
    temp = path.with_name(path.name + ".tmp")
    if temp.exists():
        raise FileExistsError("Previous temporary job remains; inspect before retrying")
    with temp.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    os.replace(temp, path)


def _context(research_root: Path) -> tuple[Path, Path, Path, Path]:
    root = research_root.resolve(strict=True)
    if root.name != RESEARCH_BASENAME or not root.is_dir():
        raise ValueError("SAFETY STOP: Only ProGrapher_Research_Private research root")
    catalog = root / CATALOG_RELATIVE
    if not catalog.is_file() or catalog.resolve(strict=True) != catalog:
        raise ValueError("SAFETY STOP: Missing or redirected test catalog copy")
    raw_dir = root / RAW_FOLDER
    if not raw_dir.is_dir() or raw_dir.resolve(strict=True) != raw_dir:
        raise ValueError("SAFETY STOP: Missing or redirected test RAW directory")
    workdir = raw_dir / JOB_FOLDER
    return root, catalog, raw_dir, workdir


def _validate_source(raw_path: Path, raw_dir: Path) -> Path:
    raw = raw_path.resolve(strict=True)
    if not raw.is_file() or raw.parent != raw_dir or raw.suffix.casefold() != ".cr3":
        raise ValueError("SAFETY STOP: Must be one CR3 research COPY in RAW_Parity_Test")
    if raw.is_symlink() or raw_path.is_symlink():
        raise ValueError("SAFETY STOP: Symlink source is not supported")
    return raw


def prepare(*, research_root: Path, raw_path: Path, overrides: dict[str, float] | None = None) -> Path:
    _, catalog, raw_dir, workdir = _context(research_root)
    raw = _validate_source(raw_path, raw_dir)
    overrides = overrides or {}
    if overrides.keys() - ADJUSTMENTS.keys():
        raise ValueError("Unsupported develop field")
    recipe: dict[str, str] = {}
    for key, (default, low, high, _) in ADJUSTMENTS.items():
        val = float(overrides.get(key, default))
        if not math.isfinite(val) or not low <= val <= high:
            raise ValueError(f"Invalid {key}")
        recipe[key] = str(val)
    job_dir = workdir / "exports"
    workdir.mkdir(exist_ok=True)
    job_dir.mkdir(exist_ok=True)
    if workdir.resolve(strict=True) != workdir or job_dir.resolve(strict=True) != job_dir:
        raise ValueError("SAFETY STOP: Work directories must not be redirected")
    if (workdir / "job.txt").exists() or (workdir / "result.txt").exists():
        raise FileExistsError("Previous LB-01 job exists. Save evidence, then remove only its job/result files manually.")
    fields = {
        "version": FORMAT_VERSION,
        "job_id": uuid4().hex,
        "catalog_path": str(catalog),
        "raw_path": str(raw),
        "raw_sha256": _digest(raw),
        "export_dir": str(job_dir),
        "profile": PROFILE,
        **recipe,
    }
    _atomic_text(workdir / "job.txt", _encode(fields))
    _atomic_text(workdir / "result.txt", _encode({"status": "prepared", "job_id": fields["job_id"]}))
    return workdir / "job.txt"


def verify(*, research_root: Path) -> tuple[bool, str]:
    _, catalog, raw_dir, workdir = _context(research_root)
    try:
        job = _read_fields(workdir / "job.txt")
        result = _read_fields(workdir / "result.txt")
    except FileNotFoundError:
        return False, "NOT READY: run prepare and Lightroom POC first"
    if set(job) != set(FILE_KEYS) or job.get("version") != FORMAT_VERSION or not ID_PATTERN.fullmatch(job.get("job_id", "")):
        return False, "FAILED: corrupt or unsupported job protocol"
    if Path(job["catalog_path"]).resolve() != catalog:
        return False, "FAILED: catalog identity mismatch"
    try:
        raw = _validate_source(Path(job["raw_path"]), raw_dir)
    except (ValueError, OSError):
        return False, "FAILED: source outside test allowlist"
    if not HASH_PATTERN.fullmatch(job["raw_sha256"]) or _digest(raw) != job["raw_sha256"]:
        return False, "FAILED: original research RAW bytes changed since prepare"
    expected_export = workdir / "exports"
    if Path(job["export_dir"]).resolve() != expected_export:
        return False, "FAILED: export directory mismatch"
    if result.get("job_id") != job["job_id"]:
        return False, "FAILED: stale result or job ID mismatch"
    if result.get("status") == "prepared":
        return False, "WAITING: run Lightroom Library > Plug-in Extras > ProGrapher LB-01 Full Recipe Test"
    if result.get("status") == "error":
        return False, "LIGHTROOM STOPPED: " + result.get("stage", "unknown") + " (see local result.txt)"
    if result.get("status") != "ok" or set(result) != set(RESULT_KEYS):
        return False, "FAILED: incomplete or invalid Lightroom result"
    if result["profile"] != PROFILE:
        return False, "FAILED: profile readback mismatch"
    for key, (_, low, high, _) in ADJUSTMENTS.items():
        try:
            target = float(job[key])
            actual = float(result[key])
        except ValueError:
            return False, f"FAILED: invalid {key}"
        tolerance = 2.0 if key == "temperature" else 1.0 if key == "tint" else 0.05
        if (not math.isfinite(target) or not math.isfinite(actual)
                or not low <= actual <= high or abs(target - actual) > tolerance):
            return False, f"FAILED: {key} readback mismatch"
    jpeg_text = result.get("jpeg", "")
    jpeg = Path(jpeg_text)
    if jpeg.parent.resolve() != expected_export or not jpeg.is_file() or jpeg.suffix.casefold() not in {".jpg", ".jpeg"}:
        return False, "FAILED: exported JPEG missing or outside destination"
    with jpeg.open("rb") as fh:
        magic = fh.read(3)
    actual_bytes = jpeg.stat().st_size
    try:
        recorded_bytes = int(result["bytes"])
    except ValueError:
        return False, "FAILED: invalid recorded JPEG size"
    if magic != b"\xff\xd8\xff" or actual_bytes < 1024 or recorded_bytes != actual_bytes:
        return False, "FAILED: invalid JPEG signature or size"
    return True, f"PASS: 10 Develop readbacks, profile, original RAW hash and {actual_bytes:,}-byte JPEG verified"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("--raw", type=Path, help="Absolute path to authorized research CR3 copy (prepare only)")
    for key, (default, _, _, _) in ADJUSTMENTS.items():
        parser.add_argument("--" + key, default=default, type=float)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            if args.raw is None:
                parser.error("prepare requires --raw pointing to the private research RAW copy")
            result = prepare(
                research_root=RESEARCH_ROOT,
                raw_path=args.raw,
                overrides={key: getattr(args, key) for key in ADJUSTMENTS},
            )
            print("PREPARED (local research job):", result)
            print("Open ONLY ProGrapher_RAW_Test.lrcat in Lightroom Classic and run the LB-01 plugin menu item.")
            return 0
        success, message = verify(research_root=RESEARCH_ROOT)
        print(message)
        return 0 if success else 2
    except (ValueError, OSError, OverflowError) as exc:
        print("SAFETY STOP:", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
