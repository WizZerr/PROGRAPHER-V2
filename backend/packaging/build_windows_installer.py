from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
PREPARE_SIDECAR = Path(__file__).resolve().with_name("prepare_tauri_sidecar.py")
NSIS_DIR = FRONTEND_DIR / "src-tauri" / "target" / "release" / "bundle" / "nsis"


def run(command: list[str], *, cwd: Path) -> None:
    print(f"\n> {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise SystemExit("npm was not found on PATH.")

    # Always rebuild/copy the packaged Python engine first so the installer
    # cannot accidentally contain a stale sidecar.
    run([sys.executable, str(PREPARE_SIDECAR)], cwd=BACKEND_DIR)

    # Build only the Windows NSIS installer for this milestone.
    run(
        [
            npm,
            "run",
            "tauri",
            "build",
            "--",
            "--bundles",
            "nsis",
        ],
        cwd=FRONTEND_DIR,
    )

    installers = sorted(
        NSIS_DIR.glob("*-setup.exe"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not installers:
        raise SystemExit(f"No NSIS installer found under: {NSIS_DIR}")

    installer = installers[0].resolve()
    print(f"\nWINDOWS_INSTALLER_READY={installer}")
    print(f"WINDOWS_INSTALLER_SIZE_BYTES={installer.stat().st_size}")


if __name__ == "__main__":
    main()
