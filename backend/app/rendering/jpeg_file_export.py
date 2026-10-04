from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import errno
import os
from pathlib import Path
import tempfile
import threading
from typing import Literal

from app.catalog.event_store import EventStore
from app.datasets.jpeg_integrity import sha256_file
from app.rendering.jpeg_export import (
    JpegEncodedArtifact,
    JpegExportOptions,
    encode_jpeg_export,
)
from app.rendering.jpeg_product_render import resolve_jpeg_product_source


JPEG_FILE_EXPORT_CONTRACT_VERSION = "jpeg-file-export-v1"
JPEG_FILE_EXPORT_COLLISION_POLICIES = {"fail", "unique"}


class JpegFileExportError(ValueError):
    pass


class JpegExportUnsafeDestination(JpegFileExportError):
    pass


class JpegExportDestinationExists(JpegFileExportError):
    pass


class JpegExportDiskFull(JpegFileExportError):
    pass


class JpegExportWriteFailed(JpegFileExportError):
    pass


class JpegExportSourceChanged(JpegFileExportError):
    pass


@dataclass(frozen=True)
class JpegFileExportResult:
    destination_path: str
    relative_path: str
    output_sha256: str
    source_sha256: str
    bytes_written: int
    collision_policy: str
    renamed_for_collision: bool
    source_unchanged: bool
    encoded: JpegEncodedArtifact


_EXPORT_LOCKS_GUARD = threading.Lock()
_EXPORT_LOCKS: dict[str, threading.Lock] = {}


def _export_lock(path: Path) -> threading.Lock:
    key = os.path.normcase(str(path))
    with _EXPORT_LOCKS_GUARD:
        lock = _EXPORT_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _EXPORT_LOCKS[key] = lock
        return lock


def _is_within(path: Path, root: Path) -> bool:
    try:
        return path == root or path.is_relative_to(root)
    except (OSError, ValueError):
        return False


def _event_source_context(
    event_id: str,
    fingerprint: str,
) -> tuple[Path, Path, Path]:
    source = resolve_jpeg_product_source(event_id, fingerprint)
    store = EventStore()
    try:
        event = store.get_event(event_id)
    except KeyError as exc:
        raise JpegExportUnsafeDestination("event not found") from exc

    event_root = Path(event.root_path).expanduser().resolve()
    try:
        relative = source.relative_to(event_root)
    except ValueError as exc:
        raise JpegExportUnsafeDestination(
            "source JPEG is outside the tracked event root"
        ) from exc

    if relative.is_absolute() or ".." in relative.parts:
        raise JpegExportUnsafeDestination(
            "source relative path is not safe for export"
        )
    return source, event_root, relative


def _resolve_output_root(output_dir: str | Path, event_root: Path) -> Path:
    try:
        root = Path(output_dir).expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        raise JpegExportUnsafeDestination(
            "export destination could not be resolved"
        ) from exc

    if root.exists() and not root.is_dir():
        raise JpegExportUnsafeDestination(
            "export destination must be a directory"
        )

    if _is_within(root, event_root):
        raise JpegExportUnsafeDestination(
            "JPEG exports must be written outside the source event folder"
        )
    return root


def _base_destination(output_root: Path, relative_source: Path) -> Path:
    destination = output_root / relative_source
    resolved_parent = destination.parent.resolve()
    if not _is_within(resolved_parent, output_root):
        raise JpegExportUnsafeDestination(
            "export path escaped the selected destination"
        )
    return destination


def _choose_destination(
    base: Path,
    collision_policy: Literal["fail", "unique"],
) -> tuple[Path, bool]:
    if collision_policy not in JPEG_FILE_EXPORT_COLLISION_POLICIES:
        raise JpegFileExportError("unsupported JPEG export collision policy")

    if not base.exists():
        return base, False

    if collision_policy == "fail":
        raise JpegExportDestinationExists(
            f"destination already exists: {base.name}"
        )

    for index in range(1, 10_000):
        candidate = base.with_name(
            f"{base.stem} ({index}){base.suffix}"
        )
        if not candidate.exists():
            return candidate, True

    raise JpegExportDestinationExists(
        "could not allocate a unique JPEG export filename"
    )


def _disk_full(exc: OSError) -> bool:
    return (
        exc.errno in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)}
        or getattr(exc, "winerror", None) == 112
    )


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        # The file itself was fsynced before promotion. Some filesystems do not
        # allow directory fsync, so lack of directory fsync support is not
        # treated as a false export failure.
        pass
    finally:
        os.close(directory_fd)


def _atomic_publish(destination: Path, payload: bytes) -> str:
    expected_sha = sha256(payload).hexdigest()
    temp_path: Path | None = None
    promoted = False

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".prographer-tmp",
            dir=str(destination.parent),
        )
        temp_path = Path(temp_name)

        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        if sha256_file(temp_path) != expected_sha:
            raise JpegExportWriteFailed(
                "temporary JPEG bytes failed integrity verification"
            )

        # Recheck immediately before promotion. ProGrapher serializes exports
        # to the same logical destination so app-internal concurrent writers
        # cannot replace one another.
        if destination.exists():
            raise JpegExportDestinationExists(
                f"destination appeared during export: {destination.name}"
            )

        os.replace(temp_path, destination)
        temp_path = None
        promoted = True
        _fsync_directory(destination.parent)

        if sha256_file(destination) != expected_sha:
            destination.unlink(missing_ok=True)
            raise JpegExportWriteFailed(
                "final JPEG bytes failed integrity verification"
            )
        return expected_sha
    except JpegFileExportError:
        raise
    except OSError as exc:
        if promoted:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
        if _disk_full(exc):
            raise JpegExportDiskFull(
                "not enough free space to complete JPEG export"
            ) from exc
        raise JpegExportWriteFailed(
            f"JPEG export write failed: {exc}"
        ) from exc
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def export_jpeg_file(
    *,
    event_id: str,
    fingerprint: str,
    recipe: dict,
    revision: int,
    options: JpegExportOptions,
    output_dir: str | Path,
    collision_policy: Literal["fail", "unique"] = "fail",
) -> JpegFileExportResult:
    source, event_root, relative_source = _event_source_context(
        event_id,
        fingerprint,
    )
    output_root = _resolve_output_root(output_dir, event_root)
    base = _base_destination(output_root, relative_source)
    source_before = sha256_file(source)

    lock = _export_lock(base)
    with lock:
        destination, renamed = _choose_destination(
            base,
            collision_policy,
        )

        if destination.resolve() == source.resolve():
            raise JpegExportUnsafeDestination(
                "export destination cannot replace the source JPEG"
            )

        encoded = encode_jpeg_export(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=recipe,
            revision=revision,
            options=options,
        )
        output_sha = _atomic_publish(destination, encoded.payload)

        source_after = sha256_file(source)
        if source_after != source_before:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
            raise JpegExportSourceChanged(
                "source JPEG changed during export; output was discarded"
            )

        return JpegFileExportResult(
            destination_path=str(destination),
            relative_path=destination.relative_to(output_root).as_posix(),
            output_sha256=output_sha,
            source_sha256=source_after,
            bytes_written=len(encoded.payload),
            collision_policy=collision_policy,
            renamed_for_collision=renamed,
            source_unchanged=True,
            encoded=encoded,
        )
