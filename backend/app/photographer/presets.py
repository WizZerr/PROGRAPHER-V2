from __future__ import annotations

import os
import platform
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LightroomPreset:
    path: str
    name: str


def _preset_roots() -> list[Path]:
    system = platform.system()
    roots: list[Path] = []

    if system == "Windows":
        appdata = os.getenv("APPDATA")
        localappdata = os.getenv("LOCALAPPDATA")

        if appdata:
            roots.extend(
                [
                    Path(appdata) / "Adobe" / "CameraRaw" / "Settings",
                    Path(appdata) / "Adobe" / "Lightroom" / "Develop Presets",
                ]
            )

        if localappdata:
            roots.append(
                Path(localappdata) / "Adobe" / "CameraRaw" / "Settings"
            )

    elif system == "Darwin":
        home = Path.home()
        roots.extend(
            [
                home
                / "Library"
                / "Application Support"
                / "Adobe"
                / "CameraRaw"
                / "Settings",
                home
                / "Library"
                / "Application Support"
                / "Adobe"
                / "Lightroom"
                / "Develop Presets",
            ]
        )

    return roots


def _preset_display_name(path: Path) -> str:
    # Lightroom XMP presets commonly expose crs:Name, but parsing must remain
    # best-effort because preset files from different versions vary.
    try:
        root = ET.parse(path).getroot()
        for element in root.iter():
            for key, value in element.attrib.items():
                if key.endswith("}Name") and value.strip():
                    return value.strip()
    except (ET.ParseError, OSError):
        pass

    return path.stem


def discover_lightroom_presets(limit: int = 250) -> list[LightroomPreset]:
    found: dict[str, LightroomPreset] = {}

    for root in _preset_roots():
        if not root.is_dir():
            continue

        try:
            paths = root.rglob("*.xmp")
        except OSError:
            continue

        for path in paths:
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                continue

            key = str(resolved)
            if os.name == "nt":
                key = key.casefold()

            found[key] = LightroomPreset(
                path=str(resolved),
                name=_preset_display_name(resolved),
            )

            if len(found) >= limit:
                break

        if len(found) >= limit:
            break

    return sorted(found.values(), key=lambda item: item.name.casefold())


def validate_preset(path: str | Path) -> LightroomPreset:
    preset = Path(path).expanduser()

    if not preset.exists() or not preset.is_file():
        raise ValueError("קובץ הפריסט שנבחר אינו קיים.")

    if preset.suffix.lower() != ".xmp":
        raise ValueError("פריסט Lightroom חייב להיות קובץ XMP.")

    resolved = preset.resolve(strict=True)

    return LightroomPreset(
        path=str(resolved),
        name=_preset_display_name(resolved),
    )
