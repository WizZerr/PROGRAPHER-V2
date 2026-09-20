from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

from app.datasets.contracts import (
    DatasetCandidate,
    DatasetPreview,
    SourceIdentity,
)
from app.datasets.xmp_reader import XmpEdit, XmpReadError, read_xmp
from app.ingest.scanner import scan_event_folder


REQUIRED_INITIAL_TARGETS = ("exposure", "temperature", "tint")


def _case_key(value: str) -> str:
    return value.casefold() if os.name == "nt" else value


def _stem_key(path: Path) -> str:
    return _case_key(str(path.with_suffix("")))


def _filename_stem(name: str) -> str:
    return _case_key(Path(name).stem)


def _source_identity(source) -> SourceIdentity:
    return SourceIdentity(
        absolute_path=source.absolute_path,
        relative_path=source.relative_path,
        filename=source.filename,
        extension=source.extension,
        size_bytes=source.size_bytes,
        modified_ns=source.modified_ns,
        fingerprint=source.fingerprint,
    )


def _missing_targets(edit: XmpEdit) -> tuple[str, ...]:
    recipe = edit.recipe
    missing: list[str] = []

    for field in REQUIRED_INITIAL_TARGETS:
        if getattr(recipe, field) is None:
            missing.append(field)

    return tuple(missing)


def build_dataset_preview(
    *,
    raw_root: str | Path,
    edits_root: str | Path,
    event_id: str,
) -> DatasetPreview:
    raw_root_path = Path(raw_root).expanduser().resolve(strict=True)
    edits_root_path = Path(edits_root).expanduser().resolve(strict=True)

    raw_sources = [
        source
        for source in scan_event_folder(raw_root_path)
        if source.source_type == "raw"
    ]

    xmp_paths = sorted(
        (
            path
            for path in edits_root_path.rglob("*")
            if path.is_file() and path.suffix.lower() == ".xmp"
        ),
        key=lambda path: str(path).casefold(),
    )

    xmp_records: list[tuple[Path, XmpEdit]] = []
    for path in xmp_paths:
        try:
            xmp_records.append((path, read_xmp(path)))
        except XmpReadError:
            # An invalid XMP is not silently paired to a RAW.
            continue

    by_relative_stem: dict[str, list[tuple[Path, XmpEdit]]] = defaultdict(list)
    by_filename_stem: dict[str, list[tuple[Path, XmpEdit]]] = defaultdict(list)
    by_declared_source: dict[str, list[tuple[Path, XmpEdit]]] = defaultdict(list)

    for xmp_path, edit in xmp_records:
        relative = xmp_path.relative_to(edits_root_path)
        by_relative_stem[_stem_key(relative)].append((xmp_path, edit))
        by_filename_stem[_filename_stem(xmp_path.name)].append(
            (xmp_path, edit)
        )

        if edit.source_filename:
            by_declared_source[
                _case_key(Path(edit.source_filename).name)
            ].append((xmp_path, edit))

    candidates: list[DatasetCandidate] = []

    for source in raw_sources:
        relative = Path(source.relative_path)
        exact = by_relative_stem.get(_stem_key(relative), [])

        declared = by_declared_source.get(
            _case_key(source.filename),
            [],
        )

        filename = by_filename_stem.get(
            _filename_stem(source.filename),
            [],
        )

        pairing_method: str | None = None
        matches: list[tuple[Path, XmpEdit]] = []

        if len(exact) == 1:
            matches = exact
            pairing_method = "relative_path_stem"
        elif len(declared) == 1:
            matches = declared
            pairing_method = "xmp_declared_source"
        elif len(filename) == 1:
            matches = filename
            pairing_method = "unique_filename_stem"
        else:
            # If any strategy has multiple candidates, ambiguity must be
            # explicit. Never choose one arbitrarily.
            ambiguous_pool = exact or declared or filename
            if len(ambiguous_pool) > 1:
                candidates.append(
                    DatasetCandidate(
                        event_id=event_id,
                        source=_source_identity(source),
                        pair_status="ambiguous",
                        xmp_path=None,
                        pairing_method=None,
                        target_recipe=None,
                        missing_target_fields=(),
                        virtual_copy_name=None,
                        final_edit_verified=False,
                        usable_for_training=False,
                    )
                )
                continue

        if not matches:
            candidates.append(
                DatasetCandidate(
                    event_id=event_id,
                    source=_source_identity(source),
                    pair_status="unmatched",
                    xmp_path=None,
                    pairing_method=None,
                    target_recipe=None,
                    missing_target_fields=(),
                    virtual_copy_name=None,
                    final_edit_verified=False,
                    usable_for_training=False,
                )
            )
            continue

        xmp_path, edit = matches[0]
        missing = _missing_targets(edit)

        candidates.append(
            DatasetCandidate(
                event_id=event_id,
                source=_source_identity(source),
                pair_status="matched",
                xmp_path=str(xmp_path.resolve()),
                pairing_method=pairing_method,
                target_recipe=edit.recipe,
                missing_target_fields=missing,
                # XMP sidecars alone do not establish Lightroom Virtual Copy
                # identity or that this is the photographer's final edit.
                virtual_copy_name=None,
                final_edit_verified=False,
                usable_for_training=False,
            )
        )

    matched = sum(item.pair_status == "matched" for item in candidates)
    unmatched = sum(item.pair_status == "unmatched" for item in candidates)
    ambiguous = sum(item.pair_status == "ambiguous" for item in candidates)

    return DatasetPreview(
        event_id=event_id,
        raw_files=len(raw_sources),
        xmp_files=len(xmp_paths),
        matched_pairs=matched,
        unmatched_raw=unmatched,
        ambiguous_raw=ambiguous,
        # Part 1 intentionally cannot claim final-edit verification.
        verified_training_pairs=0,
        candidates=tuple(candidates),
    )
