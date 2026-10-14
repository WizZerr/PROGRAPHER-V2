"""Git index guard against committing confidential photographer training assets.

Run from the repository root:
    python backend/tools/check_private_assets.py

This is a defense-in-depth guard, not a substitute for permission checks and
secret scanning. Does not inspect local untracked files or print private paths.
"""
from __future__ import annotations

import subprocess
from pathlib import PurePosixPath

RAW_EXTENSIONS = frozenset(
    "cr2 cr3 nef arw dng raf rw2 orf pef srw 3fr iiq raw nrw erf kdc mos mrw".split()
)
PRIVATE_EXTENSIONS = RAW_EXTENSIONS | {"lrcat", "xmp", "acr"}


def is_private_asset(filename: str) -> bool:
    value = filename.replace("\\", "/").casefold()
    path = PurePosixPath(value)
    suffix = path.suffix.lstrip(".")
    basename = path.name
    if suffix in PRIVATE_EXTENSIONS:
        return True
    if any(part.endswith(".lrdata") or part.endswith(".lrcat-data") for part in path.parts):
        return True
    if ".lrcat-" in basename or ".lrcat." in basename:
        return True
    if "private" in basename and suffix in {"json", "csv", "parquet", "npz", "sqlite3", "db"}:
        return True
    if any(x in path.parts for x in {"private-research", "prographer_research_private"}):
        return True
    return False


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    paths = [item.decode("utf-8", errors="replace") for item in result.stdout.split(b"\0") if item]
    private_count = sum(is_private_asset(path) for path in paths)
    if private_count:
        print(f"FAIL: {private_count} potentially private photographer assets tracked; STOP and review locally.")
        return 1
    print(f"PASS: {len(paths)} tracked paths checked for prohibited photographer assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
