from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.datasets.contracts import SourceIdentity, TargetRecipe


EditEvidenceKind = Literal[
    "master_photo",
    "virtual_copy",
    "verified_xmp",
    "manual_lightroom_reference",
]


@dataclass(frozen=True)
class LightroomEditEvidence:
    kind: EditEvidenceKind
    source_identity: SourceIdentity
    catalog_path: str | None = None
    lightroom_image_id: str | None = None
    virtual_copy_id: str | None = None
    virtual_copy_name: str | None = None
    lightroom_version: str | None = None
    target_recipe: TargetRecipe | None = None
    verification_method: str | None = None
    verified_final: bool = False


@dataclass(frozen=True)
class RoundTripCheck:
    source_fingerprint: str
    written_xmp_path: str
    source_unchanged: bool
    recipe_matches: bool
    mismatches: tuple[str, ...]
