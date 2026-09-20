from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


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


def _fingerprint(path: Path, size_bytes: int) -> str:
    """
    Stable relocation fingerprint without reading an entire large RAW.

    It uses file size + the first and last 64 KiB. This is NOT presented as a
    cryptographic content hash. A later integrity phase may compute a full hash
    where required.
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


def scan_event_folder(folder: str | Path) -> list[ScannedSource]:
    root = Path(folder).expanduser()

    if not root.exists():
        raise FolderScanError("תיקיית האירוע לא קיימת.")

    if not root.is_dir():
        raise FolderScanError("הנתיב שנבחר אינו תיקייה.")

    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise FolderScanError("לא ניתן לגשת לתיקיית האירוע.") from exc

    results: list[ScannedSource] = []

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

    for path in candidates:
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

    return results
