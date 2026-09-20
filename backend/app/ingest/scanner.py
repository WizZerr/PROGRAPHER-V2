from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


RAW_EXTENSIONS = {
    ".3fr",
    ".arw",
    ".cr2",
    ".cr3",
    ".dng",
    ".erf",
    ".fff",
    ".iiq",
    ".kdc",
    ".mef",
    ".mos",
    ".mrw",
    ".nef",
    ".nrw",
    ".orf",
    ".pef",
    ".raf",
    ".raw",
    ".rw2",
    ".rwl",
    ".sr2",
    ".srf",
    ".srw",
}

RENDERED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".png",
}

SUPPORTED_EXTENSIONS = RAW_EXTENSIONS | RENDERED_EXTENSIONS
FINGERPRINT_CHUNK_SIZE = 64 * 1024

ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class ScannedSource:
    absolute_path: str
    relative_path: str
    filename: str
    extension: str
    source_type: str
    size_bytes: int
    modified_ns: int
    fingerprint: str


class FolderScanError(ValueError):
    pass


def _resolve_root(folder: str | Path) -> Path:
    root = Path(folder).expanduser()

    if not root.exists():
        raise FolderScanError("תיקיית האירוע לא קיימת.")

    if not root.is_dir():
        raise FolderScanError("הנתיב שנבחר אינו תיקייה.")

    try:
        return root.resolve(strict=True)
    except OSError as exc:
        raise FolderScanError("לא ניתן לגשת לתיקיית האירוע.") from exc


def discover_photo_files(folder: str | Path) -> tuple[Path, list[Path]]:
    root = _resolve_root(folder)

    try:
        candidates = sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
            ),
            key=lambda path: str(path).casefold(),
        )
    except OSError as exc:
        raise FolderScanError("סריקת תיקיית האירוע נכשלה.") from exc

    return root, candidates


def _fingerprint(path: Path, size_bytes: int) -> str:
    """
    Relocation fingerprint, not a full-file integrity hash.

    Uses file size + first/last 64 KiB so large RAW folders can be indexed
    without reading every byte of every source file.
    """
    digest = hashlib.sha256()
    digest.update(str(size_bytes).encode("ascii"))
    digest.update(b"\0")

    with path.open("rb") as handle:
        digest.update(handle.read(FINGERPRINT_CHUNK_SIZE))

        if size_bytes > FINGERPRINT_CHUNK_SIZE:
            handle.seek(max(0, size_bytes - FINGERPRINT_CHUNK_SIZE))
            digest.update(handle.read(FINGERPRINT_CHUNK_SIZE))

    return digest.hexdigest()


def scan_event_folder(
    folder: str | Path,
    progress_callback: ProgressCallback | None = None,
) -> list[ScannedSource]:
    root, candidates = discover_photo_files(folder)
    total = len(candidates)

    if progress_callback:
        progress_callback(0, total, "")

    results: list[ScannedSource] = []

    for index, path in enumerate(candidates, start=1):
        try:
            stat = path.stat()
            extension = path.suffix.lower()
            source_type = "raw" if extension in RAW_EXTENSIONS else "rendered"

            results.append(
                ScannedSource(
                    absolute_path=str(path.resolve()),
                    relative_path=str(path.relative_to(root)),
                    filename=path.name,
                    extension=extension,
                    source_type=source_type,
                    size_bytes=stat.st_size,
                    modified_ns=stat.st_mtime_ns,
                    fingerprint=_fingerprint(path, stat.st_size),
                )
            )
        except (OSError, PermissionError) as exc:
            raise FolderScanError(
                f"לא ניתן לקרוא את הקובץ: {path.name}"
            ) from exc

        if progress_callback:
            progress_callback(index, total, path.name)

    return results
