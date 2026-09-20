from __future__ import annotations

import hashlib
from collections.abc import Iterable

from app.datasets.contracts import DatasetSplit


def assign_event_splits(
    event_ids: Iterable[str],
    *,
    seed: str = "prographer-dataset-v2",
    train_ratio: float = 0.8,
    validation_ratio: float = 0.1,
) -> dict[str, DatasetSplit]:
    """
    Deterministic event-level split.

    Every sample from one event must receive the same split. This function
    intentionally operates on event IDs, never on individual photographs.
    """
    unique = sorted(set(event_ids))

    if not unique:
        return {}

    if train_ratio <= 0 or validation_ratio < 0:
        raise ValueError("יחסי החלוקה אינם חוקיים.")

    if train_ratio + validation_ratio >= 1:
        raise ValueError("יש להשאיר מקום לקבוצת Test.")

    ranked = sorted(
        unique,
        key=lambda event_id: hashlib.sha256(
            f"{seed}:{event_id}".encode("utf-8")
        ).hexdigest(),
    )

    total = len(ranked)

    if total == 1:
        return {ranked[0]: "train"}

    train_count = max(1, round(total * train_ratio))
    validation_count = round(total * validation_ratio)

    if total >= 3:
        validation_count = max(1, validation_count)

    # Always preserve at least one test event once there are 2+ events.
    if train_count + validation_count >= total:
        train_count = max(1, total - validation_count - 1)

    result: dict[str, DatasetSplit] = {}

    for index, event_id in enumerate(ranked):
        if index < train_count:
            split: DatasetSplit = "train"
        elif index < train_count + validation_count:
            split = "validation"
        else:
            split = "test"

        result[event_id] = split

    return result
