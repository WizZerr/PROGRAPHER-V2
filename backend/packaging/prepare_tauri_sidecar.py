from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
TAURI_BIN_DIR = FRONTEND_DIR / "src-tauri" / "binaries"

WORK_DIR = BACKEND_DIR / "build" / "sidecar"
DIST_DIR = BACKEND_DIR / "dist" / "sidecar"


def host_triple() -> str:
    result = subprocess.run(
        ["rustc", "--print", "host-tuple"],
        capture_output=True,
        text=True,
        check=True,
    )
    value = result.stdout.strip()
    if not value:
        raise RuntimeError("rustc did not return a host tuple")
    return value


def main() -> None:
    shutil.rmtree(WORK_DIR, ignore_errors=True)
    shutil.rmtree(DIST_DIR, ignore_errors=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    TAURI_BIN_DIR.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name",
        "prographer-engine",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(WORK_DIR),
        str(BACKEND_DIR / "desktop_entry.py"),
    ]

    print("Building standalone ProGrapher sidecar...")
    subprocess.run(command, cwd=BACKEND_DIR, check=True)

    extension = ".exe" if sys.platform == "win32" else ""
    source = DIST_DIR / f"prographer-engine{extension}"

    if not source.exists():
        raise SystemExit(f"Sidecar build output not found: {source}")

    triple = host_triple()
    destination = TAURI_BIN_DIR / f"prographer-engine-{triple}{extension}"

    shutil.copy2(source, destination)

    print(f"TAURI_SIDECAR_READY={destination}")
    print(f"TARGET_TRIPLE={triple}")


if __name__ == "__main__":
    main()
