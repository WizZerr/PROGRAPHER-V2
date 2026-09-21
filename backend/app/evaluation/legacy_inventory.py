from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


TARGET_SOURCE_NAMES = {
    "vision.py",
    "profile_ai.py",
    "recipe_v2.py",
    "production_profile.py",
}

MODEL_EXTENSIONS = {
    ".pkl",
    ".pickle",
    ".joblib",
    ".pt",
    ".pth",
    ".onnx",
}


@dataclass(frozen=True)
class InventoryFile:
    relative_path: str
    size_bytes: int
    sha256: str
    kind: str
    contains_clip: bool = False
    contains_extratrees: bool = False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _source_terms(path: Path) -> tuple[bool, bool]:
    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        ).casefold()
    except OSError:
        return False, False

    return "clip" in text, "extratrees" in text


def inventory_legacy(
    legacy_root: str | Path,
) -> dict:
    root = Path(legacy_root).expanduser().resolve(strict=True)

    if not root.is_dir():
        raise ValueError("Legacy root אינו תיקייה.")

    found: list[InventoryFile] = []

    # Search is deliberately bounded to the explicitly supplied LEGACY folder.
    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if path.name in TARGET_SOURCE_NAMES:
            has_clip, has_extratrees = _source_terms(path)
            found.append(
                InventoryFile(
                    relative_path=path.relative_to(root).as_posix(),
                    size_bytes=path.stat().st_size,
                    sha256=_sha256(path),
                    kind="source",
                    contains_clip=has_clip,
                    contains_extratrees=has_extratrees,
                )
            )
            continue

        if path.suffix.casefold() in MODEL_EXTENSIONS:
            found.append(
                InventoryFile(
                    relative_path=path.relative_to(root).as_posix(),
                    size_bytes=path.stat().st_size,
                    sha256=_sha256(path),
                    kind="model_artifact",
                )
            )

    source_names = {
        Path(item.relative_path).name
        for item in found
        if item.kind == "source"
    }
    model_artifacts = [
        item for item in found if item.kind == "model_artifact"
    ]

    clip_detected = any(item.contains_clip for item in found)
    extratrees_detected = any(
        item.contains_extratrees for item in found
    )

    required_sources_present = TARGET_SOURCE_NAMES.issubset(
        source_names
    )

    reconstruction_state = (
        "candidate_for_reconstruction"
        if (
            required_sources_present
            and model_artifacts
            and clip_detected
            and extratrees_detected
        )
        else "incomplete"
    )

    return {
        "schema": "prographer.phase9.legacy-inventory.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "legacy_root": str(root),
        "required_source_names": sorted(TARGET_SOURCE_NAMES),
        "required_sources_present": required_sources_present,
        "clip_detected_in_source": clip_detected,
        "extratrees_detected_in_source": extratrees_detected,
        "model_artifact_count": len(model_artifacts),
        "reconstruction_state": reconstruction_state,
        "important_note": (
            "גם אם שחזור אפשרי, הוא מסומן reconstructed ואינו "
            "מוצג כפרופיל המקורי שהיה אצל המשתמש."
        ),
        "files": [asdict(item) for item in sorted(
            found,
            key=lambda item: item.relative_path.casefold(),
        )],
    }


def write_inventory(
    legacy_root: str | Path,
    output_path: str | Path,
) -> Path:
    payload = inventory_legacy(legacy_root)
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return destination
