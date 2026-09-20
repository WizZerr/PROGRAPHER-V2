from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
BUILD_DIR = BACKEND_DIR / "build" / "pyinstaller"
DIST_DIR = BACKEND_DIR / "dist"


def main() -> None:
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(DIST_DIR / "prographer-engine", ignore_errors=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--console",
        "--name",
        "prographer-engine",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        str(BACKEND_DIR / "desktop_entry.py"),
    ]

    print("Building ProGrapher Engine...")
    subprocess.run(command, cwd=BACKEND_DIR, check=True)

    exe_name = "prographer-engine.exe" if sys.platform == "win32" else "prographer-engine"
    output = DIST_DIR / "prographer-engine" / exe_name

    if not output.exists():
        raise SystemExit(f"Build finished but executable was not found: {output}")

    print(f"ENGINE_BUILD_OK={output}")


if __name__ == "__main__":
    main()
