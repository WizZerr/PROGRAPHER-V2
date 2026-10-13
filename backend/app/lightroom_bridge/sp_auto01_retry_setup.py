"""Create a disposable one-photo Lightroom catalog copy for SP-AUTO-01 retry.

Never modifies existing catalogs. Run ONLY with Lightroom fully closed;
PowerShell also checks no Lightroom process before invoking this script.
Copies selected catalog artifacts (not original RAWs, exports, or job evidence).
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil

from app.lightroom_bridge import sp_auto01

ROOT_NAME = "ProGrapher_Research_Private"
PARENT = "SP_01_Catalog_Test"
SOURCE = "SP_01_OFFLINE_PROOF"
DEST = "SP_01_AUTO_RETRY_01"
ARTIFACT_SUFFIXES = (".lrcat", " Smart Previews.lrdata", ".lrcat-data")


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as h:
        for data in iter(lambda: h.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def _size_safe_copytree(origin: Path, dest: Path) -> None:
    for base, dirs, files in os.walk(origin, followlinks=False):
        for child in dirs + files:
            entry = Path(base) / child
            if entry.is_symlink():
                raise ValueError("Smart Preview store contains redirect/symlink")
    shutil.copytree(origin, dest, symlinks=False)


RAW_EXTENSIONS = {
    ".cr2", ".cr3", ".nef", ".nrw", ".arw", ".srf", ".sr2",
    ".dng", ".raf", ".orf", ".rw2", ".pef", ".iiq", ".3fr",
    ".fff", ".rwl", ".erf", ".mos", ".k25", ".kdc",
}


def _snapshot_tree(folder: Path) -> dict[str, tuple[str, str]]:
    """Content-address all files and preserve empty directories. Reject links."""
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("research store missing or redirected")
    entries = {}
    for item in folder.rglob("*"):
        if item.is_symlink():
            raise ValueError("research store contains a redirect")
        rel = item.relative_to(folder).as_posix()
        if item.is_dir():
            entries[rel] = ("dir", "")
        elif item.is_file():
            entries[rel] = ("file", _fingerprint(item))
        else:
            raise ValueError("unexpected research store item")
    return entries


def _validate_staging(origin: Path, staging: Path, source_name: str,
                      dest_name: str) -> None:
    """Validate ALL copied bytes before accepting an existing staging folder.

    Lossy DNG smart preview blocks inside the exact Lightroom-owned .lrdata
    store are permitted; an original .dng or any RAW elsewhere is forbidden.
    """
    source_catalog = origin / (source_name + ".lrcat")
    staged_catalog = staging / (dest_name + ".lrcat")
    source_preview = origin / (source_name + " Smart Previews.lrdata")
    staged_preview = staging / (dest_name + " Smart Previews.lrdata")
    source_meta = origin / (source_name + ".lrcat-data")
    staged_meta = staging / (dest_name + ".lrcat-data")

    if staging.is_symlink() or not staging.is_dir():
        raise ValueError("staging missing or redirected")
    expected_names = {staged_catalog.name, staged_preview.name}
    if source_meta.exists():
        if source_meta.is_symlink() or not source_meta.is_dir():
            raise ValueError("redirected metadata store")
        expected_names.add(staged_meta.name)
    if {entry.name for entry in staging.iterdir()} != expected_names:
        raise ValueError("unexpected/missing staging artifacts")
    if (source_catalog.is_symlink() or not source_catalog.is_file()
        or staged_catalog.is_symlink() or not staged_catalog.is_file()
        or _fingerprint(source_catalog) != _fingerprint(staged_catalog)):
        raise ValueError("staged catalog is not identical to source")
    if _snapshot_tree(source_preview) != _snapshot_tree(staged_preview):
        raise ValueError("Smart Preview store clone checksum mismatch")
    if source_meta.exists():
        if _snapshot_tree(source_meta) != _snapshot_tree(staged_meta):
            raise ValueError("optional Lightroom metadata store mismatch")

    for item in staging.rglob("*"):
        if item.is_symlink():
            raise ValueError("staging contains a redirected artifact")
        if not item.is_file() or item.suffix.casefold() not in RAW_EXTENSIONS:
            continue
        if item.suffix.casefold() == ".dng" and staged_preview in item.parents:
            # Smart Previews contain Lightroom's lossy DNG blocks; do not
            # exclude the data we specifically need for offline rendering.
            continue
        raise ValueError("original RAW or unsupported RAW outside Smart Previews")


def finalize_leakage_staging(*, private_root: Path | None = None) -> Path:
    """Safely finish ONLY the existing SP03 clone after byte-for-byte validation.

    No deletion, rewriting, new catalog copy, or resume of Lightroom jobs.
    """
    root = private_root or Path.home() / "Documents" / ROOT_NAME
    if root.is_symlink():
        raise ValueError("redirected research root")
    root = root.resolve(strict=True)
    if root.name != ROOT_NAME:
        raise ValueError("invalid research root")
    research = root / PARENT
    source_name = "SP_01_AUTO_RETRY_01"
    dest_name = "SP_01_AUTO_LEAK_01"
    origin = research / source_name
    staging = research / (dest_name + ".STAGING")
    dest = research / dest_name
    if research.is_symlink() or origin.is_symlink() or not origin.is_dir():
        raise ValueError("research source unavailable or redirected")
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("SP03 catalog already exists; no overwrite")
    if not staging.is_dir() or staging.is_symlink():
        raise FileNotFoundError("no existing SP03 staging to validate")
    if any(entry.name.casefold().endswith(
        (".lock", "-wal", "-shm")
    ) for entry in origin.iterdir()):
        raise RuntimeError("source research catalog appears open")
    _validate_staging(origin, staging, source_name, dest_name)
    os.replace(staging, dest)
    return dest / (dest_name + ".lrcat")


def clone(*, private_root: Path | None = None, source_name: str = SOURCE,
          dest_name: str = DEST) -> Path:
    # Explicitly enumerated research-only copies. Never accept arbitrary names.
    allowed = {(SOURCE, DEST), ("SP_01_AUTO_RETRY_01", "SP_01_AUTO_E2E_01"),
               ("SP_01_AUTO_RETRY_01", "SP_01_AUTO_LEAK_01"),
               ("SP_01_AUTO_RETRY_01", "SP_01_AUTO_LEAK_02")}
    if (source_name, dest_name) not in allowed:
        raise ValueError("unauthorized research source/destination pair")
    root = private_root or Path.home() / "Documents" / ROOT_NAME
    if root.is_symlink():
        raise ValueError("research root symlink")
    root = root.resolve(strict=True)
    if root.name != ROOT_NAME:
        raise ValueError("research root name mismatch")
    research = root / PARENT
    origin = research / source_name
    dest = research / dest_name
    staging = research / (dest_name + ".STAGING")
    if research.is_symlink() or origin.is_symlink() or not origin.is_dir():
        raise ValueError("invalid original research folder")
    if dest.exists() or staging.exists():
        raise FileExistsError("retry copy already exists or incomplete staging")
    original_cat = origin / (source_name + ".lrcat")
    original_smart = origin / (source_name + " Smart Previews.lrdata")
    if (not original_cat.is_file() or original_cat.is_symlink()
        or not original_smart.is_dir() or original_smart.is_symlink()):
        raise ValueError("source catalog/Smart Preview research store missing")
    # A copied catalog while Lightroom is open may be silently corrupt.
    for entry in origin.iterdir():
        if (entry.name.casefold().endswith((".lock", "-wal", "-shm"))
            or entry.name.casefold().endswith((".lrcat-wal", ".lrcat-shm"))):
            raise RuntimeError("source Lightroom research catalog appears active")
    src_meta = origin / (source_name + ".lrcat-data")
    if src_meta.exists() and (src_meta.is_symlink() or not src_meta.is_dir()):
        raise ValueError("unsupported Lightroom data store")
    # Side-effect begins only after all top-level preflight passes; staging is
    # deliberately retained if copy fails; never auto-delete partial evidence.
    staging.mkdir()
    shutil.copy2(original_cat, staging / (dest_name + ".lrcat"))
    _size_safe_copytree(original_smart, staging / (dest_name + " Smart Previews.lrdata"))
    if src_meta.exists():
        _size_safe_copytree(src_meta, staging / (dest_name + ".lrcat-data"))
    if _fingerprint(original_cat) != _fingerprint(staging / (dest_name + ".lrcat")):
        raise ValueError("catalog bytes changed while cloning")
    # Check every byte; DNG blocks inside Smart Previews.lrdata are expected.
    _validate_staging(origin, staging, source_name, dest_name)
    os.replace(staging, dest)
    return dest / (dest_name + ".lrcat")


def main() -> int:
    p = argparse.ArgumentParser(description="Clone failed disposable research catalog for SP-AUTO-01 retry")
    p.add_argument("action", choices=["clone"])
    p.add_argument("--research-consent", action="store_true")
    p.add_argument("--e2e-clone", action="store_true", help="Clone cleaned SP_01_AUTO_RETRY_01 to SP_01_AUTO_E2E_01")
    p.add_argument("--leakage-clone", action="store_true", help="Clone cleaned SP_01_AUTO_RETRY_01 to SP_01_AUTO_LEAK_01")
    p.add_argument("--finalize-leakage-staging", action="store_true", help="Verify and atomically finish existing SP03 staging; never recopy or delete")
    p.add_argument("--crop-control-clone", action="store_true", help="Clone clean retry source to fresh SP03B crop-controlled test catalog")
    args = p.parse_args()
    if not args.research_consent:
        p.error("explicit local research consent required")
    if sum(bool(x) for x in (args.e2e_clone, args.leakage_clone,
                              args.finalize_leakage_staging, args.crop_control_clone)) > 1:
        p.error("Choose one research clone/finalize mode only")
    try:
        target = (clone(source_name="SP_01_AUTO_RETRY_01", dest_name="SP_01_AUTO_LEAK_02")
                  if args.crop_control_clone else
                  finalize_leakage_staging()
                  if args.finalize_leakage_staging else
                  clone(source_name="SP_01_AUTO_RETRY_01", dest_name="SP_01_AUTO_LEAK_01")
                  if args.leakage_clone else
                  clone(source_name="SP_01_AUTO_RETRY_01", dest_name="SP_01_AUTO_E2E_01")
                  if args.e2e_clone else clone())
    except (OSError, ValueError, RuntimeError, FileExistsError) as exc:
        # Only code-level failure identifiers; never print paths/photo names.
        reasons = {
            "research store missing or redirected": "STORE_MISSING_OR_REDIRECTED",
            "Smart Preview store clone checksum mismatch": "SMART_PREVIEW_HASH_MISMATCH",
            "original RAW or unsupported RAW outside Smart Previews": "UNEXPECTED_RAW_OUTSIDE_SMART_STORE",
            "unexpected/missing staging artifacts": "UNEXPECTED_STAGING_CONTENTS",
            "no existing SP03 staging to validate": "STAGING_NOT_FOUND",
        }
        reason = reasons.get(str(exc), type(exc).__name__.upper())
        p.exit(2, "SP-AUTO-03 CLONE STOPPED: " + reason + "\n")
    print("Created one new disposable Lightroom catalog without negative files.")
    print("Open the new catalog after relaunching Lightroom.")
    print("Cloned catalog basename:", target.stem)
    print("Never re-run failed SP_01_OFFLINE_PROOF job; no training.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
