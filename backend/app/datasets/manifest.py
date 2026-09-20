from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.datasets.contracts import DatasetPreview
from app.datasets.split import assign_event_splits
from app.platform.paths import user_data_dir


DATASET_MANIFEST_SCHEMA = "prographer.dataset.v2"
DATASET_MANIFEST_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def manifest_payload(
    previews: list[DatasetPreview],
    *,
    manifest_id: str | None = None,
) -> dict:
    event_ids = [preview.event_id for preview in previews]
    split_map = assign_event_splits(event_ids)

    samples = []

    for preview in previews:
        split = split_map[preview.event_id]

        for candidate in preview.candidates:
            item = asdict(candidate)
            item["split"] = split
            item["provenance"] = {
                "edit_source_type": (
                    "lightroom_xmp"
                    if candidate.xmp_path
                    else None
                ),
                "pairing_method": candidate.pairing_method,
                "final_edit_state": candidate.final_edit_state,
            }
            samples.append(item)

    return {
        "schema": DATASET_MANIFEST_SCHEMA,
        "version": DATASET_MANIFEST_VERSION,
        "manifest_id": manifest_id or uuid4().hex,
        "created_at": _utc_now(),
        "split_scope": "event",
        "initial_target_scope": [
            "exposure",
            "temperature",
            "tint",
        ],
        "events": [
            {
                "event_id": preview.event_id,
                "split": split_map[preview.event_id],
                "raw_files": preview.raw_files,
                "xmp_files": preview.xmp_files,
                "matched_pairs": preview.matched_pairs,
                "verified_training_pairs": preview.verified_training_pairs,
            }
            for preview in previews
        ],
        "samples": samples,
    }


def write_manifest(
    previews: list[DatasetPreview],
    *,
    output_dir: Path | None = None,
) -> tuple[str, Path, dict]:
    payload = manifest_payload(previews)
    manifest_id = payload["manifest_id"]

    destination_dir = (
        output_dir
        if output_dir is not None
        else user_data_dir() / "datasets" / "manifests"
    )
    destination_dir.mkdir(parents=True, exist_ok=True)

    destination = destination_dir / f"{manifest_id}.json"
    temporary = destination.with_suffix(".json.tmp")

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

    return manifest_id, destination, payload
