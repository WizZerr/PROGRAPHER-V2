from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DatasetSplit = Literal["train", "validation", "test"]
PairStatus = Literal["matched", "unmatched", "ambiguous"]


@dataclass(frozen=True)
class SourceIdentity:
    absolute_path: str
    relative_path: str
    filename: str
    extension: str
    size_bytes: int
    modified_ns: int
    fingerprint: str


@dataclass(frozen=True)
class TargetRecipe:
    exposure: float | None
    temperature: int | None
    tint: int | None
    blacks: float | None
    process_version: str | None
    camera_profile: str | None


@dataclass(frozen=True)
class DatasetCandidate:
    event_id: str
    source: SourceIdentity
    pair_status: PairStatus
    xmp_path: str | None
    pairing_method: str | None
    target_recipe: TargetRecipe | None
    missing_target_fields: tuple[str, ...]
    virtual_copy_name: str | None
    final_edit_verified: bool
    usable_for_training: bool


@dataclass(frozen=True)
class DatasetPreview:
    event_id: str
    raw_files: int
    xmp_files: int
    matched_pairs: int
    unmatched_raw: int
    ambiguous_raw: int
    verified_training_pairs: int
    candidates: tuple[DatasetCandidate, ...]
