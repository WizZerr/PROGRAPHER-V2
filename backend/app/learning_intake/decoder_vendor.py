"""Load the authorized Smart Preview decoder bundled in the repository.

The decoder's full source and tone calibration are stored as a reproducible
tar.xz source archive in backend/vendor/. This module verifies the SHA-256 and
extracts an allowlisted package to LOCAL application cache on first use.

No external download, personal Lightroom path or manual user ZIP is required.
Only the bounded DNG layer-1 decoder is called by the intake pipeline.
"""
from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

from app.platform.paths import user_data_dir

DECODER_SHA256 = "0eddbb1b6dfa0806c8df5e8e2c0325fb39de84cd1a4e4d8d4de7eda2313e6c9b"
ARCHIVE = Path(__file__).resolve().parents[2] / "vendor" / "smart_preview_decoder_source.tar.xz"
_ALLOWED = frozenset({
    "smart_preview_decoder/__init__.py",
    "smart_preview_decoder/dng.py",
    "smart_preview_decoder/render.py",
    "smart_preview_decoder/profile.py",
    "smart_preview_decoder/lens.py",
    "smart_preview_decoder/metrics.py",
    "smart_preview_decoder/data/tone_curve.json",
})
MAX_EXPANDED_BYTES = 200_000


class DecoderBundleError(RuntimeError):
    """Source archive was absent, changed or cannot be safely loaded."""


def _bundle_destination() -> Path:
    return user_data_dir() / "vendor_cache" / ("smart_preview_decoder_" + DECODER_SHA256[:16])


def _verify_archive() -> None:
    try:
        actual = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    except OSError as exc:
        raise DecoderBundleError("Bundled decoder source archive is missing.") from exc
    if actual != DECODER_SHA256:
        raise DecoderBundleError("Bundled decoder source checksum mismatch.")


def _unpack_archive(target: Path) -> None:
    """Extract exactly seven ordinary, bounded members, refusing symlinks."""
    stage_path = Path(tempfile.mkdtemp(prefix="pg-vendor-", dir=target.parent))
    try:
        with tarfile.open(ARCHIVE, mode="r:xz") as archive:
            entries = archive.getmembers()
            names = {item.name for item in entries}
            if names != _ALLOWED or len(entries) != len(_ALLOWED):
                raise DecoderBundleError("Decoder source archive has unexpected files.")
            if (any(not item.isfile() or item.size < 1 for item in entries)
                or sum(item.size for item in entries) > MAX_EXPANDED_BYTES):
                raise DecoderBundleError("Decoder source archive includes unsafe entries.")
            for item in entries:
                source = archive.extractfile(item)
                if source is None:
                    raise DecoderBundleError("Unreadable bundled decoder member.")
                data = source.read(MAX_EXPANDED_BYTES + 1)
                if len(data) != item.size:
                    raise DecoderBundleError("Bundled decoder member size mismatch.")
                # All members have already passed the strict relative-path allowlist.
                output = stage_path.joinpath(*item.name.split("/"))
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(data)
        (stage_path / ".source_checksum").write_text(DECODER_SHA256, encoding="ascii")
        try:
            os.rename(stage_path, target)
        except FileExistsError:
            # A second backend instance may have completed extraction first.
            pass
    finally:
        if stage_path.exists():
            shutil.rmtree(stage_path, ignore_errors=True)


def load_decoder_package():
    """Return the authorized package imported from its verified local cache."""
    _verify_archive()
    target = _bundle_destination()
    target.parent.mkdir(parents=True, exist_ok=True)
    marker = target / ".source_checksum"
    if not marker.is_file() or marker.read_text(encoding="ascii") != DECODER_SHA256:
        if target.exists():
            raise DecoderBundleError("Decoder cache integrity marker mismatch.")
        _unpack_archive(target)
    if not marker.is_file() or marker.read_text(encoding="ascii") != DECODER_SHA256:
        raise DecoderBundleError("Decoder source extraction did not complete.")
    location = str(target)
    if location not in sys.path:
        sys.path.insert(0, location)
    active = sys.modules.get("smart_preview_decoder")
    if active is not None:
        current = str(getattr(active, "__file__", ""))
        if not current.startswith(location + os.sep):
            raise DecoderBundleError("Another Smart Preview decoder is already loaded.")
        return active
    try:
        return importlib.import_module("smart_preview_decoder")
    except Exception as exc:
        raise DecoderBundleError("Cannot import bundled decoder source.") from exc
