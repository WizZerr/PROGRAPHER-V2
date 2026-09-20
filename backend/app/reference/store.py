from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.datasets.contracts import SourceIdentity, TargetRecipe
from app.platform.paths import user_data_dir
from app.reference.contracts import ReferenceCase, ReferenceRender


REFERENCE_SCHEMA = "prographer.reference.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def register_lightroom_render(
    *,
    source: SourceIdentity,
    recipe: TargetRecipe,
    render_path: str | Path,
    color_space: str,
    file_format: str,
    process_family: str,
    lightroom_version: str | None = None,
    output_dir: str | Path | None = None,
) -> tuple[ReferenceCase, Path]:
    render_file = Path(render_path).expanduser().resolve(strict=True)

    if not render_file.is_file():
        raise ValueError("קובץ רינדור ה-Lightroom שנבחר אינו קובץ.")

    render = ReferenceRender(
        render_path=str(render_file),
        render_sha256=_sha256(render_file),
        render_kind="lightroom_export",
        color_space=color_space,
        file_format=file_format,
        lightroom_version=lightroom_version,
        created_from_recipe=recipe,
    )

    case = ReferenceCase(
        case_id=uuid4().hex,
        source=source,
        recipe=recipe,
        process_family=process_family,
        camera_profile=recipe.camera_profile,
        render=render,
        status="reference_registered",
    )

    destination_dir = (
        Path(output_dir).expanduser().resolve()
        if output_dir is not None
        else user_data_dir() / "references"
    )
    destination_dir.mkdir(parents=True, exist_ok=True)

    destination = destination_dir / f"{case.case_id}.json"
    temporary = destination.with_suffix(".json.tmp")

    payload = {
        "schema": REFERENCE_SCHEMA,
        "version": 1,
        "created_at": _utc_now(),
        **asdict(case),
    }

    temporary.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    os.replace(temporary, destination)

    return case, destination
