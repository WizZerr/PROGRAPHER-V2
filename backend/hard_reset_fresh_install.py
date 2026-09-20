from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


def read_env_value(key: str) -> str | None:
    # Environment wins, matching the backend.
    direct = os.getenv(key)
    if direct is not None and direct.strip():
        return direct.strip()

    if not ENV_FILE.exists():
        return None

    for raw in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, value = line.split("=", 1)
        if k.strip() != key:
            continue
        value = value.strip().strip('"').strip("'")
        return value
    return None


def resolve_data_dir() -> Path:
    configured = read_env_value("PROGRAPHER_DATA_DIR") or "./data"
    path = Path(configured)
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    else:
        path = path.resolve()
    return path


def unsafe_target(path: Path) -> str | None:
    root = Path(path.anchor).resolve() if path.anchor else None
    home = Path.home().resolve()
    base = BASE_DIR.resolve()

    if root and path == root:
        return "drive/root directory"
    if path == home:
        return "user home directory"
    if path == base:
        return "backend source directory"
    if path in base.parents:
        return "parent of backend source directory"
    # Do not allow deleting an extremely broad path like C:\\Users or D:\\.
    if len(path.parts) <= 2:
        return "path is too broad"
    return None


def main() -> int:
    if "--confirmed" not in sys.argv:
        print("ERROR: This script must be launched from HARD_RESET_FRESH_INSTALL.bat")
        return 2

    data_dir = resolve_data_dir()
    reason = unsafe_target(data_dir)
    if reason:
        print(f"REFUSING RESET: {data_dir}")
        print(f"Safety reason: {reason}")
        return 3

    print()
    print("Resolved ProGrapher data directory:")
    print(f"  {data_dir}")
    print()

    if data_dir.exists():
        try:
            shutil.rmtree(data_dir)
        except Exception as exc:
            print("ERROR: Could not delete the ProGrapher data directory.")
            print("Make sure start_backend.bat / Python is completely closed.")
            print(f"Reason: {exc}")
            return 4

    data_dir.mkdir(parents=True, exist_ok=True)

    leftovers = list(data_dir.iterdir())
    if leftovers:
        print("ERROR: Data directory is not empty after reset.")
        for item in leftovers[:20]:
            print(f" - {item}")
        return 5

    print("FACTORY DATA RESET COMPLETE")
    print("The configured data directory is now completely empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
