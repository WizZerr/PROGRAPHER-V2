from pathlib import Path
import os
import platform


def user_data_dir() -> Path:
    system = platform.system()

    if system == "Windows":
        base = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "ProGrapher"

    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "ProGrapher"

    return Path(
        os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    ) / "ProGrapher"


def user_cache_dir() -> Path:
    system = platform.system()

    if system == "Windows":
        base = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "ProGrapher" / "Cache"

    if system == "Darwin":
        return Path.home() / "Library" / "Caches" / "ProGrapher"

    return Path(
        os.getenv("XDG_CACHE_HOME") or Path.home() / ".cache"
    ) / "ProGrapher"
