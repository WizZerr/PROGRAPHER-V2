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


def clone(*, private_root: Path | None = None) -> Path:
    root = private_root or Path.home() / "Documents" / ROOT_NAME
    if root.is_symlink():
        raise ValueError("research root symlink")
    root = root.resolve(strict=True)
    if root.name != ROOT_NAME:
        raise ValueError("research root name mismatch")
    research = root / PARENT
    origin = research / SOURCE
    dest = research / DEST
    staging = research / (DEST + ".STAGING")
    if research.is_symlink() or origin.is_symlink() or not origin.is_dir():
        raise ValueError("invalid original research folder")
    if dest.exists() or staging.exists():
        raise FileExistsError("retry copy already exists or incomplete staging")
    original_cat = origin / (SOURCE + ".lrcat")
    original_smart = origin / (SOURCE + " Smart Previews.lrdata")
    if (not original_cat.is_file() or original_cat.is_symlink()
        or not original_smart.is_dir() or original_smart.is_symlink()):
        raise ValueError("source catalog/Smart Preview research store missing")
    # A copied catalog while Lightroom is open may be silently corrupt.
    for entry in origin.iterdir():
        if (entry.name.casefold().endswith((".lock", "-wal", "-shm"))
            or entry.name.casefold().endswith((".lrcat-wal", ".lrcat-shm"))):
            raise RuntimeError("source Lightroom research catalog appears active")
    src_meta = origin / (SOURCE + ".lrcat-data")
    if src_meta.exists() and (src_meta.is_symlink() or not src_meta.is_dir()):
        raise ValueError("unsupported Lightroom data store")
    # Side-effect begins only after all top-level preflight passes; staging is
    # deliberately retained if copy fails; never auto-delete partial evidence.
    staging.mkdir()
    shutil.copy2(original_cat, staging / (DEST + ".lrcat"))
    _size_safe_copytree(original_smart, staging / (DEST + " Smart Previews.lrdata"))
    if src_meta.exists():
        _size_safe_copytree(src_meta, staging / (DEST + ".lrcat-data"))
    if _fingerprint(original_cat) != _fingerprint(staging / (DEST + ".lrcat")):
        raise ValueError("catalog bytes changed while cloning")
    # Ensure original RAW copies never get copied across.
    if list(staging.rglob("*.CR3")) or list(staging.rglob("*.cr3")):
        raise ValueError("RAW copy unexpectedly present in staging")
    os.replace(staging, dest)
    return dest / (DEST + ".lrcat")


def main() -> int:
    p = argparse.ArgumentParser(description="Clone failed disposable research catalog for SP-AUTO-01 retry")
    p.add_argument("action", choices=["clone"])
    p.add_argument("--research-consent", action="store_true")
    args = p.parse_args()
    if not args.research_consent:
        p.error("explicit local research consent required")
    try:
        target = clone()
    except (OSError, ValueError, RuntimeError, FileExistsError) as exc:
        p.exit(2, "SP-AUTO-01 RETRY SETUP STOPPED: " + type(exc).__name__ + "\n")
    print("Created one new disposable Lightroom catalog without negative files.")
    print("Open the new catalog after relaunching Lightroom.")
    print("Never re-run failed SP_01_OFFLINE_PROOF job; no training.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
