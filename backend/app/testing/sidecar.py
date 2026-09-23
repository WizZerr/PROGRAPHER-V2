from __future__ import annotations

import hashlib
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from app.datasets.contracts import TargetRecipe
from app.lightroom_bridge.xmp_roundtrip import CRS_NS, X_NS, RDF_NS, _recipe_attrs


EXPORT_MARKER = "testing-loop-v1"
MARKER_FIELD = "ProGrapherExport"


class SidecarExportError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _marker_present(path: Path) -> bool:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return False
    marker = f"{{{CRS_NS}}}{MARKER_FIELD}"
    for element in root.iter():
        if element.attrib.get(marker) == EXPORT_MARKER:
            return True
    return False


def write_testing_sidecar(
    *,
    raw_path: str | Path,
    relative_path: str,
    recipe: TargetRecipe,
    output_dir: str | Path,
) -> Path:
    """
    Write a Lightroom sidecar into a folder the tester chose.

    The RAW file is opened only to hash it. It is never written.
    An existing XMP is replaced only when this loop wrote it before.
    """
    raw = Path(raw_path).expanduser().resolve(strict=True)
    if not raw.is_file():
        raise SidecarExportError(f"קובץ המקור אינו קיים: {raw}")

    destination_root = Path(output_dir).expanduser().resolve()
    destination_root.mkdir(parents=True, exist_ok=True)

    relative = Path(relative_path)
    destination = destination_root / relative.with_suffix(".xmp")
    if destination.resolve() == raw.resolve():
        raise SidecarExportError("ייצוא לא יכול להחליף את קובץ ה-RAW.")

    if destination.exists() and not _marker_present(destination):
        raise SidecarExportError(
            "כבר קיים XMP שלא נוצר על ידי ProGrapher, והוא לא הוחלף."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    before = _sha256(raw)

    attrs = _recipe_attrs(recipe)
    if recipe.temperature is not None or recipe.tint is not None:
        attrs[f"{{{CRS_NS}}}WhiteBalance"] = "Custom"
    attrs[f"{{{CRS_NS}}}{MARKER_FIELD}"] = EXPORT_MARKER

    xmpmeta = ET.Element(f"{{{X_NS}}}xmpmeta")
    rdf = ET.SubElement(xmpmeta, f"{{{RDF_NS}}}RDF")
    description = ET.SubElement(rdf, f"{{{RDF_NS}}}Description", attrs)
    description.set(f"{{{CRS_NS}}}RawFileName", raw.name)
    description.set(f"{{{CRS_NS}}}HasSettings", "True")

    temporary = destination.with_suffix(destination.suffix + ".tmp")
    ET.ElementTree(xmpmeta).write(
        temporary,
        encoding="utf-8",
        xml_declaration=True,
    )
    os.replace(temporary, destination)

    after = _sha256(raw)
    if before != after:
        destination.unlink(missing_ok=True)
        raise SidecarExportError("קובץ ה-RAW השתנה במהלך הייצוא והפעולה בוטלה.")

    return destination
