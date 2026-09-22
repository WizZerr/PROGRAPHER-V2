from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DatasetManifestSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_id: str
    event_id: str

    raw_path: str
    raw_relpath: str
    raw_sha256: str

    xmp_path: str | None
    xmp_relpath: str | None
    xmp_sha256: str | None

    pair_status: str
    target_status: str
    ready_for_three_target_training: bool

    targets: dict[str, float | int | None] | None = None
    missing_target_fields: tuple[str, ...] = ()
    rendering_context: dict[str, Any] | None = None
    error: str | None = None


class DatasetImportManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "phase12-dataset-manifest-v1"
    dataset_id: str
    dataset_root: str

    sample_count: int
    training_ready_count: int
    event_count: int
    usable_event_ids: tuple[str, ...]
    event_safe_split_ready: bool

    source_readiness_schema_version: str
    samples: tuple[DatasetManifestSample, ...]

    guardrails: tuple[str, ...] = Field(
        default=(
            "Manifest identity is content-derived and deterministic.",
            "No model training is performed while building this manifest.",
            "No missing target value is replaced with zero.",
            "Event grouping is preserved for later event-safe splitting.",
        )
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_sample_id(
    *,
    event_id: str,
    raw_sha256: str,
    xmp_sha256: str | None,
) -> str:
    payload = {
        "event_id": event_id,
        "raw_sha256": raw_sha256,
        "xmp_sha256": xmp_sha256,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _relative(path_value: str | None, root: Path) -> str | None:
    if path_value is None:
        return None
    path = Path(path_value).resolve()
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def build_dataset_manifest_from_readiness(
    report: dict[str, Any],
) -> DatasetImportManifest:
    schema = report.get("schema_version")
    if schema != "phase12-dataset-readiness-v1":
        raise ValueError(
            f"Unsupported readiness schema: {schema!r}"
        )

    root = Path(report["root"]).resolve()
    rows = report.get("rows")
    if not isinstance(rows, list):
        raise ValueError("Readiness report rows must be a list")

    samples: list[DatasetManifestSample] = []

    for row in rows:
        raw_path = Path(row["raw_path"]).resolve()
        if not raw_path.is_file():
            raise ValueError(
                f"RAW disappeared after readiness scan: {raw_path}"
            )

        raw_sha256 = row.get("raw_sha256")
        if not raw_sha256:
            raw_sha256 = _sha256_file(raw_path)

        xmp_path_value = row.get("xmp_path")
        xmp_path = (
            Path(xmp_path_value).resolve()
            if xmp_path_value
            else None
        )
        xmp_sha256 = None
        if xmp_path is not None:
            if not xmp_path.is_file():
                raise ValueError(
                    f"XMP disappeared after readiness scan: {xmp_path}"
                )
            xmp_sha256 = _sha256_file(xmp_path)

        sample = DatasetManifestSample(
            sample_id=_stable_sample_id(
                event_id=row["event_id"],
                raw_sha256=raw_sha256,
                xmp_sha256=xmp_sha256,
            ),
            event_id=row["event_id"],
            raw_path=str(raw_path),
            raw_relpath=_relative(str(raw_path), root) or raw_path.name,
            raw_sha256=raw_sha256,
            xmp_path=str(xmp_path) if xmp_path else None,
            xmp_relpath=_relative(
                str(xmp_path) if xmp_path else None,
                root,
            ),
            xmp_sha256=xmp_sha256,
            pair_status=row["pair_status"],
            target_status=row["target_status"],
            ready_for_three_target_training=bool(
                row["ready_for_three_target_training"]
            ),
            targets=row.get("targets"),
            missing_target_fields=tuple(
                row.get("missing_target_fields") or ()
            ),
            rendering_context=row.get("rendering_context"),
            error=row.get("error"),
        )
        samples.append(sample)

    samples.sort(
        key=lambda item: (
            item.event_id.lower(),
            item.raw_relpath.lower(),
            item.sample_id,
        )
    )

    usable_event_ids = tuple(
        sorted(
            {
                item.event_id
                for item in samples
                if item.ready_for_three_target_training
            }
        )
    )

    identity_payload = {
        "schema_version": "phase12-dataset-manifest-v1",
        "samples": [
            {
                "sample_id": item.sample_id,
                "event_id": item.event_id,
                "raw_sha256": item.raw_sha256,
                "xmp_sha256": item.xmp_sha256,
                "targets": item.targets,
                "rendering_context": item.rendering_context,
                "ready": item.ready_for_three_target_training,
            }
            for item in samples
        ],
    }
    dataset_id = hashlib.sha256(
        json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return DatasetImportManifest(
        dataset_id=dataset_id,
        dataset_root=str(root),
        sample_count=len(samples),
        training_ready_count=sum(
            1 for item in samples
            if item.ready_for_three_target_training
        ),
        event_count=len(
            {item.event_id for item in samples}
        ),
        usable_event_ids=usable_event_ids,
        event_safe_split_ready=len(usable_event_ids) >= 2,
        source_readiness_schema_version=schema,
        samples=tuple(samples),
    )
