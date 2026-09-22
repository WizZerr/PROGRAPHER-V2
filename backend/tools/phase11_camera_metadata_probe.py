from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def probe_exifread(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "provider": "exifread",
        "available": False,
        "error": None,
        "make": None,
        "model": None,
        "lens_model": None,
        "captured_at": None,
        "matched_keys": {},
    }
    try:
        import exifread  # type: ignore
    except Exception as exc:
        result["error"] = f"import_failed: {type(exc).__name__}: {exc}"
        return result

    result["available"] = True
    try:
        with path.open("rb") as f:
            tags = exifread.process_file(f, details=False)

        candidates = {
            "make": [
                "Image Make",
                "EXIF Make",
                "QuickTime Make",
            ],
            "model": [
                "Image Model",
                "EXIF Model",
                "QuickTime Model",
            ],
            "lens_model": [
                "EXIF LensModel",
                "Image LensModel",
            ],
            "captured_at": [
                "EXIF DateTimeOriginal",
                "EXIF DateTimeDigitized",
                "Image DateTime",
            ],
        }

        for field, keys in candidates.items():
            for key in keys:
                if key in tags:
                    value = clean(tags[key])
                    if value is not None:
                        result[field] = value
                        result["matched_keys"][field] = key
                        break

        # Keep only a narrow diagnostic inventory of camera-ish keys.
        interesting = {}
        for key, value in tags.items():
            low = key.lower()
            if any(token in low for token in ("make", "model", "camera", "lens", "serial")):
                interesting[key] = clean(value)
        result["camera_related_tags"] = interesting
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def probe_rawpy(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "provider": "rawpy-libraw",
        "available": False,
        "error": None,
        "raw_type": None,
        "metadata_attrs": {},
    }
    try:
        import rawpy  # type: ignore
    except Exception as exc:
        result["error"] = f"import_failed: {type(exc).__name__}: {exc}"
        return result

    result["available"] = True
    try:
        with rawpy.imread(str(path)) as raw:
            result["raw_type"] = type(raw).__name__

            # Intentionally inspect only plausible metadata fields if exposed.
            for name in (
                "camera_make",
                "camera_model",
                "make",
                "model",
                "lens",
                "lens_model",
                "metadata",
            ):
                if hasattr(raw, name):
                    try:
                        value = getattr(raw, name)
                        result["metadata_attrs"][name] = clean(value)
                    except Exception as exc:
                        result["metadata_attrs"][name] = f"<error: {type(exc).__name__}: {exc}>"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def probe_exiftool(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "provider": "exiftool-cli",
        "available": False,
        "executable": None,
        "error": None,
        "make": None,
        "model": None,
        "lens_model": None,
        "captured_at": None,
    }
    exe = shutil.which("exiftool")
    if exe is None:
        exe = shutil.which("exiftool.exe")
    if exe is None:
        return result

    result["available"] = True
    result["executable"] = exe
    try:
        cp = subprocess.run(
            [
                exe,
                "-j",
                "-Make",
                "-Model",
                "-LensModel",
                "-DateTimeOriginal",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if cp.returncode != 0:
            result["error"] = f"return_code={cp.returncode}: {cp.stderr.strip()}"
            return result

        rows = json.loads(cp.stdout)
        row = rows[0] if rows else {}
        result["make"] = clean(row.get("Make"))
        result["model"] = clean(row.get("Model"))
        result["lens_model"] = clean(row.get("LensModel"))
        result["captured_at"] = clean(row.get("DateTimeOriginal"))
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe reliable camera identity sources on a real RAW without guessing from the filename."
    )
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    path = args.raw.resolve()
    if not path.is_file():
        raise SystemExit(f"RAW not found: {path}")

    providers = [
        probe_exifread(path),
        probe_rawpy(path),
        probe_exiftool(path),
    ]

    report = {
        "schema_version": "phase11-camera-metadata-probe-v1",
        "source": str(path),
        "filename_is_not_used_as_camera_identity": True,
        "providers": providers,
    }

    print("\n=== Phase 11 camera metadata probe ===")
    print(f"RAW: {path}")
    print("Filename inference: DISABLED")
    print()

    for item in providers:
        print(f"[{item['provider']}]")
        print(f"  available: {item.get('available')}")
        print(f"  make: {item.get('make')}")
        print(f"  model: {item.get('model')}")
        print(f"  lens_model: {item.get('lens_model')}")
        print(f"  captured_at: {item.get('captured_at')}")
        if item.get("metadata_attrs"):
            print(f"  rawpy metadata attrs: {item['metadata_attrs']}")
        if item.get("matched_keys"):
            print(f"  matched keys: {item['matched_keys']}")
        if item.get("error"):
            print(f"  error: {item['error']}")
        print()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Report: {args.output.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
