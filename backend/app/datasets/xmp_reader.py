from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from app.datasets.contracts import TargetRecipe


@dataclass(frozen=True)
class XmpEdit:
    path: str
    source_filename: str | None
    recipe: TargetRecipe


class XmpReadError(ValueError):
    pass


def _local_name(name: str) -> str:
    if "}" in name:
        return name.rsplit("}", 1)[-1]
    if ":" in name:
        return name.rsplit(":", 1)[-1]
    return name


def _attributes(root: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}

    for element in root.iter():
        for key, value in element.attrib.items():
            local = _local_name(key)
            # First concrete value wins; do not silently override with another
            # namespace occurrence later in the document.
            values.setdefault(local, value)

    return values


def _optional_float(
    values: dict[str, str],
    *keys: str,
) -> float | None:
    for key in keys:
        if key not in values:
            continue

        raw = values[key].strip()
        if raw == "":
            return None

        try:
            return float(raw)
        except ValueError as exc:
            raise XmpReadError(
                f"ערך XMP לא חוקי בשדה {key}: {raw}"
            ) from exc

    return None


def _optional_int(
    values: dict[str, str],
    *keys: str,
) -> int | None:
    value = _optional_float(values, *keys)
    if value is None:
        return None
    return int(round(value))


def _optional_text(
    values: dict[str, str],
    *keys: str,
) -> str | None:
    for key in keys:
        value = values.get(key)
        if value is not None and value.strip():
            return value.strip()
    return None


def read_xmp(path: str | Path) -> XmpEdit:
    xmp = Path(path).expanduser()

    if not xmp.exists() or not xmp.is_file():
        raise XmpReadError("קובץ XMP אינו קיים.")

    try:
        root = ET.parse(xmp).getroot()
    except (ET.ParseError, OSError) as exc:
        raise XmpReadError(
            f"לא ניתן לקרוא את קובץ XMP: {xmp.name}"
        ) from exc

    values = _attributes(root)

    # Missing stays None. A real zero remains 0 / 0.0.
    recipe = TargetRecipe(
        exposure=_optional_float(values, "Exposure2012", "Exposure"),
        temperature=_optional_int(values, "Temperature"),
        tint=_optional_int(values, "Tint"),
        blacks=_optional_float(values, "Blacks2012", "Blacks"),
        process_version=_optional_text(values, "ProcessVersion"),
        camera_profile=_optional_text(
            values,
            "CameraProfile",
            "ProfileName",
        ),
    )

    return XmpEdit(
        path=str(xmp.resolve()),
        source_filename=_optional_text(
            values,
            "RawFileName",
            "SourceFile",
            "OriginalFileName",
        ),
        recipe=recipe,
    )
