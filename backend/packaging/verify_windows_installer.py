from __future__ import annotations

import hashlib
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
NSIS_DIR = (
    PROJECT_DIR
    / "frontend"
    / "src-tauri"
    / "target"
    / "release"
    / "bundle"
    / "nsis"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    installers = sorted(
        NSIS_DIR.glob("*-setup.exe"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not installers:
        raise SystemExit(f"No NSIS installer found under: {NSIS_DIR}")

    installer = installers[0].resolve()

    if installer.stat().st_size < 1_000_000:
        raise SystemExit(
            f"Installer looks unexpectedly small: {installer.stat().st_size} bytes"
        )

    print(f"INSTALLER={installer}")
    print(f"SIZE_BYTES={installer.stat().st_size}")
    print(f"SHA256={sha256(installer)}")
    print("INSTALLER_ARTIFACT_CHECK_OK")


if __name__ == "__main__":
    main()
