from __future__ import annotations

import argparse
import os
import re
import sqlite3
from pathlib import Path

from app.datasets.contracts import TargetRecipe
from app.lightroom_bridge.xmp_roundtrip import write_reference_xmp


_NUMBER_RE = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"


def _number(text: str, *keys: str) -> float | None:
    for key in keys:
        match = re.search(
            rf"(?m)^\s*{re.escape(key)}\s*=\s*({_NUMBER_RE})\s*,?\s*$",
            text,
        )
        if match:
            return float(match.group(1))
    return None


def _string(text: str, *keys: str) -> str | None:
    for key in keys:
        match = re.search(
            rf'(?m)^\s*{re.escape(key)}\s*=\s*"([^"]*)"\s*,?\s*$',
            text,
        )
        if match:
            return match.group(1)
    return None


def _recipe(text: str) -> TargetRecipe | None:
    exposure = _number(text, "Exposure2012", "Exposure")
    temperature = _number(text, "Temperature", "CustomTemperature")
    tint = _number(text, "Tint", "CustomTint")

    # PR1 deliberately requires these first three targets to be present.
    if exposure is None or temperature is None or tint is None:
        return None

    blacks = _number(text, "Blacks2012", "Blacks")
    process_version = _string(text, "ProcessVersion")
    if process_version is None:
        raw_process = _number(text, "ProcessVersion")
        process_version = f"{raw_process:g}" if raw_process is not None else None

    return TargetRecipe(
        exposure=float(exposure),
        temperature=int(round(temperature)),
        tint=int(round(tint)),
        blacks=float(blacks) if blacks is not None else None,
        process_version=process_version,
        camera_profile=_string(text, "CameraProfile"),
    )


def _catalog_rows(db: sqlite3.Connection, collection: str):
    return db.execute(
        """
        SELECT
            f.baseName,
            f.extension,
            d.text
        FROM AgLibraryCollection c
        JOIN AgLibraryCollectionImage ci
            ON ci.collection = c.id_local
        JOIN Adobe_images i
            ON i.id_local = ci.image
        JOIN AgLibraryFile f
            ON f.id_local = i.rootFile
        JOIN Adobe_imageDevelopSettings d
            ON d.id_local = i.developSettingsIDCache
        WHERE c.name = ?
          AND lower(f.extension) = 'dng'
        ORDER BY f.baseName
        """,
        (collection,),
    ).fetchall()


def _build_source_index(raw_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    duplicates: set[str] = set()

    for path in raw_root.rglob("*.dng"):
        key = path.stem.casefold()
        if key in index:
            duplicates.add(key)
        else:
            index[key] = path

    for key in duplicates:
        index.pop(key, None)

    return index


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a small RAW+XMP PR1 QA fixture from the local FiveK Lightroom "
            "catalog without modifying the FiveK source files."
        )
    )
    parser.add_argument("--catalog", required=True, help="Path to fivek.lrcat")
    parser.add_argument("--raw-root", required=True, help="Root containing FiveK DNG files")
    parser.add_argument("--output", required=True, help="Destination fixture folder")
    parser.add_argument("--collection", default="C", help="Lightroom collection to use")
    parser.add_argument("--count", type=int, default=50, help="Number of usable pairs")
    args = parser.parse_args()

    catalog = Path(args.catalog).expanduser().resolve(strict=True)
    raw_root = Path(args.raw_root).expanduser().resolve(strict=True)
    output = Path(args.output).expanduser().resolve()
    raw_out = output / "raw"
    xmp_out = output / "xmp"
    raw_out.mkdir(parents=True, exist_ok=True)
    xmp_out.mkdir(parents=True, exist_ok=True)

    source_index = _build_source_index(raw_root)

    db = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
    try:
        rows = _catalog_rows(db, args.collection)
    finally:
        db.close()

    created = 0
    skipped_missing_recipe = 0
    skipped_missing_raw = 0

    for base_name, _extension, settings_text in rows:
        if created >= args.count:
            break

        recipe = _recipe(settings_text or "")
        if recipe is None:
            skipped_missing_recipe += 1
            continue

        source = source_index.get(str(base_name).casefold())
        if source is None:
            skipped_missing_raw += 1
            continue

        destination = raw_out / source.name
        if not destination.exists():
            try:
                os.link(source, destination)
            except OSError as exc:
                raise RuntimeError(
                    "Could not create an NTFS hard link for the DNG. Keep the fixture "
                    "on the same drive as FiveK and try again. "
                    f"Source: {source} Destination: {destination}"
                ) from exc

        write_reference_xmp(
            raw_path=destination,
            recipe=recipe,
            output_dir=xmp_out,
        )
        created += 1

    print("=" * 72)
    print("FiveK -> PR1 RAW+XMP QA fixture")
    print("=" * 72)
    print(f"Collection:              {args.collection}")
    print(f"Catalog rows:            {len(rows)}")
    print(f"Usable pairs created:    {created}")
    print(f"Missing first 3 targets: {skipped_missing_recipe}")
    print(f"Missing/duplicate DNG:   {skipped_missing_raw}")
    print(f"RAW folder:              {raw_out}")
    print(f"XMP folder:              {xmp_out}")
    print()
    print("The DNG files are NTFS hard links, so the fixture does not duplicate the RAW data.")
    print("The source FiveK catalog and source DNG files were opened read-only / not modified.")

    if created < args.count:
        raise SystemExit(
            f"Requested {args.count} pairs but only created {created}."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
