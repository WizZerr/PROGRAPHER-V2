from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.ingest.scanner import ScannedSource, scan_event_folder


JPEG_EXTENSIONS = {".jpg", ".jpeg"}


@dataclass(frozen=True)
class JpegPair:
    original_path: str
    edited_path: str
    original_relative_path: str
    edited_relative_path: str
    original_fingerprint: str
    edited_fingerprint: str


@dataclass(frozen=True)
class JpegPairScan:
    original_files: int
    edited_files: int
    matched_pairs: int
    unmatched_files: int
    ambiguous_files: int
    identical_pairs: int
    ignored_non_jpeg: int
    pairs: tuple[JpegPair, ...]


def _case_key(value: str) -> str:
    # Camera filenames are identifiers for pairing, not filesystem lookups.
    # Treat case consistently on Windows and macOS so IMG_0001.JPG and
    # img_0001.jpg do not become different photos merely because the host OS
    # has different case semantics.
    return value.casefold()


def _relative_stem(root: Path, path: Path) -> str:
    relative = path.resolve().relative_to(root.resolve())
    return _case_key(str(relative.with_suffix("")))


def _filename_stem(name: str) -> str:
    return _case_key(Path(name).stem)


def _pair(
    originals_root: Path,
    edits_root: Path,
    original: ScannedSource,
    edited: ScannedSource,
) -> JpegPair:
    return JpegPair(
        original_path=original.absolute_path,
        edited_path=edited.absolute_path,
        original_relative_path=str(
            Path(original.absolute_path).resolve().relative_to(originals_root)
        ),
        edited_relative_path=str(
            Path(edited.absolute_path).resolve().relative_to(edits_root)
        ),
        original_fingerprint=original.fingerprint,
        edited_fingerprint=edited.fingerprint,
    )


def scan_jpeg_pairs(originals_root: str | Path, edits_root: str | Path) -> JpegPairScan:
    originals = Path(originals_root).expanduser().resolve(strict=True)
    edits = Path(edits_root).expanduser().resolve(strict=True)

    original_sources = scan_event_folder(originals)
    edited_sources = scan_event_folder(edits)

    jpeg_originals = [
        source
        for source in original_sources
        if source.extension in JPEG_EXTENSIONS
    ]
    jpeg_edits = [
        source
        for source in edited_sources
        if source.extension in JPEG_EXTENSIONS
    ]
    ignored = (
        len(original_sources) - len(jpeg_originals)
        + len(edited_sources) - len(jpeg_edits)
    )

    by_relative: dict[str, list[ScannedSource]] = defaultdict(list)
    by_filename: dict[str, list[ScannedSource]] = defaultdict(list)
    for source in jpeg_edits:
        by_relative[_relative_stem(edits, Path(source.absolute_path))].append(source)
        by_filename[_filename_stem(source.filename)].append(source)

    unmatched = 0
    ambiguous = 0
    identical = 0
    candidate_pairs: list[JpegPair] = []

    for source in jpeg_originals:
        relative_key = _relative_stem(originals, Path(source.absolute_path))
        filename_key = _filename_stem(source.filename)
        exact = by_relative.get(relative_key, [])
        named = by_filename.get(filename_key, [])

        if len(exact) == 1:
            chosen = exact[0]
        elif len(named) == 1:
            chosen = named[0]
        elif len(exact) > 1 or len(named) > 1:
            ambiguous += 1
            continue
        else:
            unmatched += 1
            continue

        # Selecting the exact same physical file as both "original" and
        # "edited" is a configuration mistake. Different files with identical
        # bytes remain valid: an intentionally unchanged photo is still a
        # meaningful identity target.
        if Path(source.absolute_path).resolve() == Path(chosen.absolute_path).resolve():
            identical += 1
            continue

        candidate_pairs.append(_pair(originals, edits, source, chosen))

    by_edit_path: dict[str, list[JpegPair]] = defaultdict(list)
    for pair in candidate_pairs:
        by_edit_path[pair.edited_path].append(pair)

    pairs: list[JpegPair] = []
    for group in by_edit_path.values():
        if len(group) == 1:
            pairs.append(group[0])
        else:
            # One final image cannot be the target for two different originals.
            ambiguous += len(group)

    return JpegPairScan(
        original_files=len(jpeg_originals),
        edited_files=len(jpeg_edits),
        matched_pairs=len(pairs),
        unmatched_files=unmatched,
        ambiguous_files=ambiguous,
        identical_pairs=identical,
        ignored_non_jpeg=ignored,
        pairs=tuple(pairs),
    )
