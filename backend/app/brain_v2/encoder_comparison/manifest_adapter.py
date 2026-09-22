from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.brain_v2.encoder_comparison.contracts import ComparisonDataset


@dataclass(frozen=True)
class ManifestSample:
    sample_id: str
    source_path: str
    event_group: str
    split: str
    exposure_ev: float
    temperature_k: float
    tint: float
    camera: dict[str, Any]
    exif: dict[str, Any]
    raw_info: dict[str, Any]
    capture_time: str | None


@dataclass(frozen=True)
class ManifestSelection:
    dataset: ComparisonDataset
    samples: tuple[ManifestSample, ...]
    manifest_total: int
    selected_total: int
    excluded_test: int

    def validate(self) -> None:
        self.dataset.validate()
        if len(self.samples) != self.selected_total:
            raise ValueError("selected_total אינו תואם למספר הדוגמאות.")
        if tuple(item.sample_id for item in self.samples) != self.dataset.sample_ids:
            raise ValueError("סדר samples אינו תואם ל-ComparisonDataset.")


def _load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise ValueError("Dataset V2 manifest ריק.")

    if path.suffix.casefold() in {".jsonl", ".ndjson"}:
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(
                    f"JSONL line {line_number} אינו object."
                )
            records.append(value)
        return records

    payload = json.loads(text)

    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and isinstance(payload.get("samples"), list):
        records = payload["samples"]
    else:
        raise ValueError(
            "JSON manifest חייב להיות array או object עם samples."
        )

    if not all(isinstance(item, dict) for item in records):
        raise ValueError("כל Dataset sample חייב להיות object.")

    return list(records)


def _required_text(
    record: dict[str, Any],
    field: str,
    *,
    sample_hint: str,
) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{sample_hint}: field '{field}' חסר או ריק."
        )
    return value.strip()


def _target_number(
    recipe: dict[str, Any],
    field: str,
    *,
    sample_id: str,
) -> float:
    if field not in recipe or recipe[field] is None:
        raise ValueError(
            f"{sample_id}: target_recipe.{field} חסר."
        )

    value = recipe[field]

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"{sample_id}: target_recipe.{field} אינו מספר."
        )

    numeric = float(value)
    if not np.isfinite(numeric):
        raise ValueError(
            f"{sample_id}: target_recipe.{field} מכיל NaN/Inf."
        )

    # Zero is a valid target. Never use truthiness checks here.
    return numeric


def _parse_sample(record: dict[str, Any], index: int) -> ManifestSample:
    hint = f"sample[{index}]"
    sample_id = _required_text(record, "sample_id", sample_hint=hint)
    source_path = _required_text(
        record,
        "source_path",
        sample_hint=sample_id,
    )
    event_group = _required_text(
        record,
        "event_group",
        sample_hint=sample_id,
    )
    split = _required_text(
        record,
        "split",
        sample_hint=sample_id,
    ).casefold()

    if split not in {"train", "validation", "test"}:
        raise ValueError(
            f"{sample_id}: split לא נתמך: {split}"
        )

    recipe = record.get("target_recipe")
    if not isinstance(recipe, dict):
        raise ValueError(
            f"{sample_id}: target_recipe חסר או אינו object."
        )

    camera = record.get("camera") or {}
    exif = record.get("exif") or {}
    raw_info = record.get("raw_info") or {}

    if not isinstance(camera, dict):
        raise ValueError(f"{sample_id}: camera אינו object.")
    if not isinstance(exif, dict):
        raise ValueError(f"{sample_id}: exif אינו object.")
    if not isinstance(raw_info, dict):
        raise ValueError(f"{sample_id}: raw_info אינו object.")

    capture_time = record.get("capture_time")
    if capture_time is not None and not isinstance(capture_time, str):
        raise ValueError(
            f"{sample_id}: capture_time חייב להיות string/null."
        )

    return ManifestSample(
        sample_id=sample_id,
        source_path=source_path,
        event_group=event_group,
        split=split,
        exposure_ev=_target_number(
            recipe,
            "exposure",
            sample_id=sample_id,
        ),
        temperature_k=_target_number(
            recipe,
            "temperature",
            sample_id=sample_id,
        ),
        tint=_target_number(
            recipe,
            "tint",
            sample_id=sample_id,
        ),
        camera=dict(camera),
        exif=dict(exif),
        raw_info=dict(raw_info),
        capture_time=capture_time,
    )


def load_dataset_v2_manifest(
    path: str | Path,
) -> ManifestSelection:
    manifest_path = Path(path).expanduser().resolve(strict=True)
    records = _load_records(manifest_path)

    parsed = tuple(
        _parse_sample(record, index)
        for index, record in enumerate(records)
    )

    sample_ids = [item.sample_id for item in parsed]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("Dataset V2 מכיל sample_id כפול.")

    selected = tuple(
        item
        for item in parsed
        if item.split in {"train", "validation"}
    )
    excluded_test = sum(
        1 for item in parsed if item.split == "test"
    )

    if not selected:
        raise ValueError(
            "לא נמצאו samples של train/validation."
        )

    dataset = ComparisonDataset(
        sample_ids=tuple(item.sample_id for item in selected),
        event_ids=tuple(item.event_group for item in selected),
        splits=tuple(item.split for item in selected),
        targets=np.asarray(
            [
                (
                    item.exposure_ev,
                    item.temperature_k,
                    item.tint,
                )
                for item in selected
            ],
            dtype=np.float32,
        ),
    )
    dataset.validate()

    result = ManifestSelection(
        dataset=dataset,
        samples=selected,
        manifest_total=len(parsed),
        selected_total=len(selected),
        excluded_test=excluded_test,
    )
    result.validate()
    return result
