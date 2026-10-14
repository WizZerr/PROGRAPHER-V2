"""Safe, inventory-only probe for Lightroom Classic Smart Previews.lrdata.

Never treats directory presence, a matching name, or an arbitrary cache file as
proof of a matched photo or a source-neutral (unedited) image.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class SmartPreviewsProbe:
    path: str
    exists: bool
    readable: bool
    asset_files: int
    total_bytes: int
    name_matches_catalog: bool
    identity_verified: bool
    note: str


def probe_smart_previews(
    preview_dir: str | Path, *, catalog_path: str | Path
) -> SmartPreviewsProbe:
    directory = Path(preview_dir).expanduser()
    catalog = Path(catalog_path).expanduser()
    directory_path = str(directory)
    invalid = lambda reason: SmartPreviewsProbe(
        path=directory_path, exists=directory.exists(), readable=False,
        asset_files=0, total_bytes=0, name_matches_catalog=False,
        identity_verified=False, note=reason
    )
    try:
        if directory.is_symlink():
            return invalid("Smart Previews path is a symbolic link; rejected")
        if not directory.is_dir():
            return invalid("Smart Previews folder is missing or not a directory")
        if not directory.name.casefold().endswith(" smart previews.lrdata"):
            return invalid("Select Lightroom Smart Previews.lrdata, not ordinary Previews.lrdata")
        expected = (catalog.stem + " Smart Previews.lrdata").casefold()
        name_match = directory.name.casefold() == expected
        if not name_match:
            return invalid("Smart Previews folder name does not match the selected catalog")

        files = 0
        total_bytes = 0
        directories = [directory]
        while directories:
            current = directories.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        return invalid("Smart Previews contains symbolic links; rejected")
                    if entry.is_dir(follow_symlinks=False):
                        directories.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        files += 1
                        total_bytes += entry.stat(follow_symlinks=False).st_size
                    else:
                        return invalid("Smart Previews contains an unsupported filesystem entry")
        if files == 0:
            return invalid("Smart Previews directory contains no files")
        return SmartPreviewsProbe(
            path=str(directory.resolve()), exists=True, readable=True,
            asset_files=files, total_bytes=total_bytes,
            name_matches_catalog=True, identity_verified=False,
            note="File inventory only; Lightroom photo identity and source neutrality are NOT verified."
        )
    except (OSError, ValueError) as exc:
        return invalid("Smart Previews read failed: " + type(exc).__name__)
