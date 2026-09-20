from __future__ import annotations

import hashlib
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from app.datasets.contracts import TargetRecipe
from app.datasets.xmp_reader import read_xmp
from app.lightroom_bridge.contracts import RoundTripCheck


X_NS = "adobe:ns:meta/"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
CRS_NS = "http://ns.adobe.com/camera-raw-settings/1.0/"

ET.register_namespace("x", X_NS)
ET.register_namespace("rdf", RDF_NS)
ET.register_namespace("crs", CRS_NS)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _recipe_attrs(recipe: TargetRecipe) -> dict[str, str]:
    attrs: dict[str, str] = {}

    if recipe.exposure is not None:
        attrs[f"{{{CRS_NS}}}Exposure2012"] = f"{recipe.exposure:g}"

    if recipe.temperature is not None:
        attrs[f"{{{CRS_NS}}}Temperature"] = str(recipe.temperature)

    if recipe.tint is not None:
        attrs[f"{{{CRS_NS}}}Tint"] = str(recipe.tint)

    if recipe.blacks is not None:
        attrs[f"{{{CRS_NS}}}Blacks2012"] = f"{recipe.blacks:g}"

    if recipe.process_version is not None:
        attrs[f"{{{CRS_NS}}}ProcessVersion"] = recipe.process_version

    if recipe.camera_profile is not None:
        attrs[f"{{{CRS_NS}}}CameraProfile"] = recipe.camera_profile

    return attrs


def write_reference_xmp(
    *,
    raw_path: str | Path,
    recipe: TargetRecipe,
    output_dir: str | Path,
) -> Path:
    """
    Write a test/reference XMP into a separate work directory.

    This function intentionally never writes beside or inside the RAW file.
    """
    raw = Path(raw_path).expanduser().resolve(strict=True)
    destination_dir = Path(output_dir).expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)

    destination = destination_dir / f"{raw.stem}.prographer-reference.xmp"
    temporary = destination.with_suffix(destination.suffix + ".tmp")

    xmpmeta = ET.Element(f"{{{X_NS}}}xmpmeta")
    rdf = ET.SubElement(xmpmeta, f"{{{RDF_NS}}}RDF")
    description = ET.SubElement(
        rdf,
        f"{{{RDF_NS}}}Description",
        _recipe_attrs(recipe),
    )
    description.set(f"{{{CRS_NS}}}RawFileName", raw.name)

    tree = ET.ElementTree(xmpmeta)
    tree.write(
        temporary,
        encoding="utf-8",
        xml_declaration=True,
    )
    os.replace(temporary, destination)

    return destination


def compare_recipe(
    expected: TargetRecipe,
    actual: TargetRecipe,
) -> tuple[str, ...]:
    mismatches: list[str] = []

    if expected.exposure is None:
        if actual.exposure is not None:
            mismatches.append("exposure")
    elif actual.exposure is None or abs(expected.exposure - actual.exposure) > 1e-9:
        mismatches.append("exposure")

    for field in (
        "temperature",
        "tint",
        "process_version",
        "camera_profile",
    ):
        if getattr(expected, field) != getattr(actual, field):
            mismatches.append(field)

    if expected.blacks is None:
        if actual.blacks is not None:
            mismatches.append("blacks")
    elif actual.blacks is None or abs(expected.blacks - actual.blacks) > 1e-9:
        mismatches.append("blacks")

    return tuple(mismatches)


def run_reference_roundtrip(
    *,
    raw_path: str | Path,
    recipe: TargetRecipe,
    output_dir: str | Path,
) -> RoundTripCheck:
    raw = Path(raw_path).expanduser().resolve(strict=True)
    before = _sha256(raw)

    xmp_path = write_reference_xmp(
        raw_path=raw,
        recipe=recipe,
        output_dir=output_dir,
    )

    read_back = read_xmp(xmp_path)
    mismatches = compare_recipe(recipe, read_back.recipe)

    after = _sha256(raw)

    return RoundTripCheck(
        source_fingerprint=before,
        written_xmp_path=str(xmp_path),
        source_unchanged=before == after,
        recipe_matches=len(mismatches) == 0,
        mismatches=mismatches,
    )
