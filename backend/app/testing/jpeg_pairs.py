from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.ingest.scanner import scan_event_folder


JPEG_EXTENSIONS = {".jpg", ".jpeg"}


@dataclass(frozen=True)
class JpegPairScan:
    original_files: int
    edited_files: int
    matched_pairs: int
    unmatched_files: int
    ambiguous_files: int
    ignored_non_jpeg: int


def _case_key(value: str) -> str:
    return value.casefold() if os.name == "nt" else value


def _relative_stem(root: Path, path: Path) -> str:
    relative = path.resolve().relative_to(root.resolve())
    return _case_key(str(relative.with_suffix("")))


def _filename_stem(name: str) -> str:
    return _case_key(Path(name).stem)


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
    ignored = len(original_sources) - len(jpeg_originals)

    by_relative: dict[str, list] = defaultdict(list)
    by_filename: dict[str, list] = defaultdict(list)
    for source in jpeg_edits:
        by_relative[_relative_stem(edits, Path(source.absolute_path))].append(source)
        by_filename[_filename_stem(source.filename)].append(source)

    matched = 0
    unmatched = 0
    ambiguous = 0
    used_edit_paths: dict[str, int] = defaultdict(int)

    for source in jpeg_originals:
        relative_key = _relative_stem(originals, Path(source.absolute_path))
        filename_key = _filename_stem(source.filename)
        exact = by_relative.get(relative_key, [])
        named = by_filename.get(filename_key, [])

        if len(exact) == 1:
            chosen = exact
        elif len(named) == 1:
            chosen = named
        elif len(exact) > 1 or len(named) > 1:
            ambiguous += 1
            continue
        else:
            unmatched += 1
            continue

        matched += 1
        used_edit_paths[chosen[0].absolute_path] += 1

    shared_originals = sum(
        count for count in used_edit_paths.values() if count > 1
    )
    if shared_originals:
        matched -= shared_originals
        ambiguous += shared_originals

    return JpegPairScan(
        original_files=len(jpeg_originals),
        edited_files=len(jpeg_edits),
        matched_pairs=max(0, matched),
        unmatched_files=unmatched,
        ambiguous_files=ambiguous,
        ignored_non_jpeg=ignored,
    )
