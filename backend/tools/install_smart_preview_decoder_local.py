"""Install a USER-SUPPLIED research decoder ZIP into the current venv only.

The author's code and calibration data are intentionally NOT committed.
Run only on trusted files with the author's permission. Does NOT install pip
dependencies, execute embedded scripts or modify Lightroom content.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import sysconfig
import tempfile
import zipfile
from pathlib import Path

ROOT = "smart_preview_decoder_pkg/smart_preview_decoder/"
FILES = {
    "__init__.py", "dng.py", "render.py", "profile.py", "lens.py",
    "metrics.py", "data/tone_curve.json",
}
MAX_TOTAL_BYTES = 2 * 1024 * 1024


def install(zip_path: Path) -> Path:
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Activate the project-specific Python .venv first.")
    zip_path = zip_path.resolve(strict=True)
    destination = Path(sysconfig.get_path("purelib")) / "smart_preview_decoder"
    if destination.exists():
        raise RuntimeError(
            f"Local decoder already installed at {destination}. "
            "Do not overwrite it automatically."
        )
    if zip_path.stat().st_size > MAX_TOTAL_BYTES:
        raise RuntimeError("Unexpectedly large decoder ZIP; installation blocked.")
    with zipfile.ZipFile(zip_path) as archive:
        selected = {}
        total = 0
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            if not entry.filename.startswith(ROOT):
                continue
            relative = entry.filename[len(ROOT):]
            if relative not in FILES or relative in selected:
                raise RuntimeError("Unexpected or duplicate file inside decoder module.")
            if entry.file_size > MAX_TOTAL_BYTES:
                raise RuntimeError("Oversized module member.")
            total += entry.file_size
            if total > MAX_TOTAL_BYTES:
                raise RuntimeError("Expanded module exceeds safety limit.")
            selected[relative] = archive.read(entry)
        if set(selected) != FILES:
            raise RuntimeError(
                "Decoder ZIP does not contain the expected seven source/data files."
            )
    # Never write to the main project, Lightroom, or a system Python.
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pg-decoder-", dir=destination.parent) as work:
        stage = Path(work) / "smart_preview_decoder"
        stage.mkdir()
        for rel, data in selected.items():
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        shutil.copytree(stage, destination)
    print("Installed optional source-only DNG decoder in this venv:", destination)
    print("Module archive SHA-256:", hashlib.sha256(zip_path.read_bytes()).hexdigest())
    print("Separate codec dependency still required: python -m pip install tifffile imagecodecs")
    print("No Lightroom source or photo files were modified.")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True, dest="zip_path")
    opts = parser.parse_args()
    try:
        install(opts.zip_path)
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        parser.exit(2, f"Installation blocked: {error}\n")
