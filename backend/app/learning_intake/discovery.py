"""Bounded, read-only discovery of Lightroom catalog siblings.

Adobe Lightroom Classic normally puts "<catalog> Smart Previews.lrdata"
beside "<catalog>.lrcat". A matching directory name is NOT verification of
image identity, contents, JPEG XL decoding or training readiness.
"""
from __future__ import annotations

from pathlib import Path

from app.learning_intake.service import LearningIntakeError

MAX_CATALOGS_PER_DIRECTORY = 128


def find_smart_previews(catalog: Path) -> Path | None:
    """Only use an unambiguous, exact-stem sibling Smart Previews directory."""
    if not catalog.is_file() or catalog.suffix.casefold() != ".lrcat":
        raise LearningIntakeError("Choose a Lightroom .lrcat file.")
    target = (catalog.stem + " Smart Previews.lrdata").casefold()
    matches: list[Path] = []
    try:
        for entry in catalog.parent.iterdir():
            if entry.name.casefold() != target:
                continue
            if entry.is_symlink() or not entry.is_dir():
                continue
            matches.append(entry.resolve(strict=True))
    except OSError as exc:
        raise LearningIntakeError("Cannot inspect sibling Smart Previews paths.") from exc

    # Never guess if case-insensitive paths are ambiguous on this filesystem.
    return matches[0] if len(matches) == 1 else None


def discover_catalogs(path_value: str) -> dict:
    """Inspect one chosen .lrcat or its parent folder, non-recursively.

    Does not open preview bytes; does not write or persist any data.
    Multiple .lrcat files must be explicitly selected by the photographer.
    """
    requested = Path(path_value).expanduser()
    if requested.is_symlink():
        raise LearningIntakeError("Symbolic-link locations are not accepted.")
    try:
        path = requested.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LearningIntakeError("Chosen catalog location is unavailable.") from exc
    if path.is_file():
        if path.suffix.casefold() != ".lrcat":
            raise LearningIntakeError("Select a Lightroom .lrcat file or its folder.")
        catalogs = [path]
    elif path.is_dir():
        if path.name.casefold().endswith(".lrdata"):
            raise LearningIntakeError("Select the catalog folder, not its .lrdata folder.")
        try:
            catalogs = [
                child.resolve(strict=True) for child in path.iterdir()
                if not child.is_symlink() and child.is_file()
                and child.suffix.casefold() == ".lrcat"
            ]
        except OSError as exc:
            raise LearningIntakeError("Unable to read the chosen catalog folder.") from exc
        if len(catalogs) > MAX_CATALOGS_PER_DIRECTORY:
            raise LearningIntakeError("Too many catalogs here. Select the .lrcat file directly.")
        catalogs.sort(key=lambda item: item.name.casefold())
    else:
        raise LearningIntakeError("Select a Lightroom catalog file or folder.")

    if not catalogs:
        raise LearningIntakeError("No .lrcat file found in this folder. Select its parent catalog folder.")

    return {
        "catalogs": [{
            "catalog_path": str(catalog),
            "smart_previews_path": str(previews) if (
                previews := find_smart_previews(catalog)
            ) else None,
            "preview_detection": "name_match_unverified" if previews else "not_found",
        } for catalog in catalogs],
        "requires_selection": len(catalogs) != 1,
        "note": "Only exact-name adjacent Smart Previews are detected; contents and image links are not verified.",
    }
