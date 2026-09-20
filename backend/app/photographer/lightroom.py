from __future__ import annotations

import os
import platform
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LightroomInstallation:
    detected: bool
    application_path: str | None
    source: str | None


@dataclass(frozen=True)
class LightroomCatalogProbe:
    path: str
    exists: bool
    readable: bool
    sqlite_valid: bool
    catalog_photo_records: int | None
    note: str


def _windows_registry_lightroom() -> str | None:
    if platform.system() != "Windows":
        return None

    try:
        import winreg
    except ImportError:
        return None

    roots = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    subkeys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]

    for root in roots:
        for base in subkeys:
            try:
                with winreg.OpenKey(root, base) as key:
                    index = 0
                    while True:
                        try:
                            name = winreg.EnumKey(key, index)
                            index += 1
                        except OSError:
                            break

                        try:
                            with winreg.OpenKey(key, name) as app_key:
                                display_name, _ = winreg.QueryValueEx(
                                    app_key, "DisplayName"
                                )
                                if "Lightroom Classic" not in str(display_name):
                                    continue

                                try:
                                    install_location, _ = winreg.QueryValueEx(
                                        app_key, "InstallLocation"
                                    )
                                except OSError:
                                    install_location = ""

                                install = Path(str(install_location))
                                candidates = [
                                    install / "Lightroom.exe",
                                    install / "Adobe Lightroom Classic.exe",
                                ]
                                for candidate in candidates:
                                    if candidate.is_file():
                                        return str(candidate)
                        except OSError:
                            continue
            except OSError:
                continue

    return None


def detect_lightroom() -> LightroomInstallation:
    system = platform.system()

    if system == "Windows":
        registry_path = _windows_registry_lightroom()
        if registry_path:
            return LightroomInstallation(
                detected=True,
                application_path=registry_path,
                source="windows_registry",
            )

        program_files = [
            os.getenv("ProgramFiles"),
            os.getenv("ProgramFiles(x86)"),
        ]

        for base in filter(None, program_files):
            adobe = Path(base) / "Adobe"
            if not adobe.is_dir():
                continue

            try:
                matches = sorted(
                    adobe.glob("Adobe Lightroom Classic*"),
                    reverse=True,
                )
            except OSError:
                matches = []

            for folder in matches:
                for exe_name in (
                    "Lightroom.exe",
                    "Adobe Lightroom Classic.exe",
                ):
                    exe = folder / exe_name
                    if exe.is_file():
                        return LightroomInstallation(
                            detected=True,
                            application_path=str(exe),
                            source="standard_install_path",
                        )

    if system == "Darwin":
        applications = Path("/Applications")
        try:
            matches = sorted(
                applications.glob("Adobe Lightroom Classic*.app"),
                reverse=True,
            )
        except OSError:
            matches = []

        if matches:
            return LightroomInstallation(
                detected=True,
                application_path=str(matches[0]),
                source="applications_folder",
            )

    return LightroomInstallation(
        detected=False,
        application_path=None,
        source=None,
    )


def discover_default_catalogs() -> list[str]:
    pictures = Path.home() / "Pictures"
    candidates: list[Path] = []

    for base in (pictures / "Lightroom", pictures):
        if not base.is_dir():
            continue

        try:
            candidates.extend(base.glob("*.lrcat"))
        except OSError:
            continue

    unique = {
        str(path.resolve())
        for path in candidates
        if path.is_file()
    }

    return sorted(unique, key=str.casefold)


def probe_catalog(path: str | Path) -> LightroomCatalogProbe:
    catalog = Path(path).expanduser()

    if not catalog.exists():
        return LightroomCatalogProbe(
            path=str(catalog),
            exists=False,
            readable=False,
            sqlite_valid=False,
            catalog_photo_records=None,
            note="קטלוג Lightroom שנבחר אינו קיים.",
        )

    if not catalog.is_file():
        return LightroomCatalogProbe(
            path=str(catalog),
            exists=True,
            readable=False,
            sqlite_valid=False,
            catalog_photo_records=None,
            note="הנתיב שנבחר אינו קובץ קטלוג.",
        )

    if catalog.suffix.lower() != ".lrcat":
        return LightroomCatalogProbe(
            path=str(catalog.resolve()),
            exists=True,
            readable=True,
            sqlite_valid=False,
            catalog_photo_records=None,
            note="הקובץ אינו קטלוג Lightroom מסוג .lrcat.",
        )

    try:
        uri = catalog.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as db:
            db.execute("PRAGMA query_only = ON")

            row = db.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'Adobe_images'
                """
            ).fetchone()

            if row is None:
                return LightroomCatalogProbe(
                    path=str(catalog.resolve()),
                    exists=True,
                    readable=True,
                    sqlite_valid=True,
                    catalog_photo_records=None,
                    note=(
                        "הקטלוג נפתח, אך מבנה Adobe_images לא זוהה. "
                        "לא נסיק מכך מספר דוגמאות אימון."
                    ),
                )

            count = int(
                db.execute("SELECT COUNT(*) FROM Adobe_images").fetchone()[0]
            )

        return LightroomCatalogProbe(
            path=str(catalog.resolve()),
            exists=True,
            readable=True,
            sqlite_valid=True,
            catalog_photo_records=count,
            note=(
                "נספרו רשומות צילום בקטלוג בלבד. "
                "זה אינו מספר עריכות סופיות או דוגמאות אימון תקינות."
            ),
        )
    except (sqlite3.Error, OSError) as exc:
        return LightroomCatalogProbe(
            path=str(catalog.resolve()),
            exists=True,
            readable=False,
            sqlite_valid=False,
            catalog_photo_records=None,
            note=f"לא ניתן לקרוא את הקטלוג במצב קריאה בלבד: {exc}",
        )
