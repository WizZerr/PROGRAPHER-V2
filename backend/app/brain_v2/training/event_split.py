from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.brain_v2.training.dataset_manifest import DatasetImportManifest


SplitName = Literal["train", "validation"]


class EventSplitAssignment(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    split: SplitName
    stable_score_hex: str


class SampleSplitAssignment(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_id: str
    event_id: str
    split: SplitName


class EventSafeSplitManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "phase12-event-safe-split-v1"
    split_id: str
    dataset_id: str
    seed: str
    validation_fraction: float

    train_event_ids: tuple[str, ...]
    validation_event_ids: tuple[str, ...]
    event_assignments: tuple[EventSplitAssignment, ...]
    sample_assignments: tuple[SampleSplitAssignment, ...]

    train_sample_count: int
    validation_sample_count: int

    guardrails: tuple[str, ...] = Field(
        default=(
            "Split assignment is performed at event level only.",
            "A usable event can never appear in both train and validation.",
            "Only samples marked ready_for_three_target_training receive a split.",
            "The same dataset_id + seed + validation_fraction reproduces the same split.",
        )
    )


def _event_score(seed: str, event_id: str) -> str:
    payload = f"{seed}\0{event_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validation_count(event_count: int, validation_fraction: float) -> int:
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be between 0 and 1")
    if event_count < 2:
        raise ValueError(
            "At least two usable events are required for an event-safe split"
        )

    proposed = round(event_count * validation_fraction)
    return min(event_count - 1, max(1, proposed))


def build_event_safe_split(
    manifest: DatasetImportManifest,
    *,
    validation_fraction: float = 0.20,
    seed: str = "phase12-v1",
) -> EventSafeSplitManifest:
    seed = seed.strip()
    if not seed:
        raise ValueError("seed must be non-empty")

    usable_events = sorted(set(manifest.usable_event_ids))
    validation_count = _validation_count(
        len(usable_events),
        validation_fraction,
    )

    ranked = sorted(
        (
            (_event_score(seed, event_id), event_id)
            for event_id in usable_events
        ),
        key=lambda item: (item[0], item[1].lower()),
    )

    validation_events = {
        event_id
        for _, event_id in ranked[:validation_count]
    }
    train_events = {
        event_id
        for _, event_id in ranked[validation_count:]
    }

    overlap = train_events & validation_events
    if overlap:
        raise AssertionError(
            f"Event leakage detected: {sorted(overlap)}"
        )

    event_assignments = tuple(
        EventSplitAssignment(
            event_id=event_id,
            split=(
                "validation"
                if event_id in validation_events
                else "train"
            ),
            stable_score_hex=score,
        )
        for score, event_id in ranked
    )

    sample_assignments_list: list[SampleSplitAssignment] = []
    for sample in manifest.samples:
        if not sample.ready_for_three_target_training:
            continue
        if sample.event_id in validation_events:
            split: SplitName = "validation"
        elif sample.event_id in train_events:
            split = "train"
        else:
            raise ValueError(
                "Training-ready sample belongs to an event absent from "
                f"usable_event_ids: {sample.event_id}"
            )

        sample_assignments_list.append(
            SampleSplitAssignment(
                sample_id=sample.sample_id,
                event_id=sample.event_id,
                split=split,
            )
        )

    sample_assignments = tuple(
        sorted(
            sample_assignments_list,
            key=lambda item: (
                item.event_id.lower(),
                item.sample_id,
            ),
        )
    )

    train_event_ids = tuple(sorted(train_events))
    validation_event_ids = tuple(sorted(validation_events))

    identity_payload = {
        "schema_version": "phase12-event-safe-split-v1",
        "dataset_id": manifest.dataset_id,
        "seed": seed,
        "validation_fraction": validation_fraction,
        "train_event_ids": train_event_ids,
        "validation_event_ids": validation_event_ids,
        "sample_assignments": [
            item.model_dump(mode="json")
            for item in sample_assignments
        ],
    }
    split_id = hashlib.sha256(
        json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return EventSafeSplitManifest(
        split_id=split_id,
        dataset_id=manifest.dataset_id,
        seed=seed,
        validation_fraction=validation_fraction,
        train_event_ids=train_event_ids,
        validation_event_ids=validation_event_ids,
        event_assignments=event_assignments,
        sample_assignments=sample_assignments,
        train_sample_count=sum(
            1 for item in sample_assignments
            if item.split == "train"
        ),
        validation_sample_count=sum(
            1 for item in sample_assignments
            if item.split == "validation"
        ),
    )
