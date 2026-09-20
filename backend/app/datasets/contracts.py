from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DatasetSplit = Literal["train", "validation", "test"]
PairStatus = Literal["matched", "unmatched", "ambiguous"]
FinalEditState = Literal["unreviewed", "verified_final", "rejected"]
PermissionBasis = Literal[
    "unspecified",
    "photographer_owned",
    "client_permission",
    "licensed_dataset",
    "other",
]


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
class SourceMetadata:
    camera_make: str | None = None
    camera_model: str | None = None
    captured_at: str | None = None
    iso: int | None = None
    shutter_seconds: float | None = None
    aperture: float | None = None
    focal_length_mm: float | None = None
    raw_wb: tuple[float, ...] | None = None
    raw_wb_source: str | None = None


@dataclass(frozen=True)
class TargetRecipe:
    exposure: float | None
    temperature: int | None
    tint: int | None
    blacks: float | None
    process_version: str | None
    camera_profile: str | None


@dataclass(frozen=True)
class DatasetRights:
    permission_basis: PermissionBasis = "unspecified"
    allow_personal_training: bool = False
    allow_general_training: bool = False
    license_name: str | None = None
    notes: str | None = None


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
    final_edit_state: FinalEditState
    final_edit_verified: bool
    has_local_adjustments: bool
    exclusion_reasons: tuple[str, ...]
    usable_for_training: bool
    source_metadata: SourceMetadata | None = None
    photographer_id: str | None = None
    sequence_id: str | None = None
    lightroom_version: str | None = None
    style_label: str | None = None


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
