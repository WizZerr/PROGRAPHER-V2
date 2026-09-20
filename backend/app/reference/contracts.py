from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.datasets.contracts import SourceIdentity, TargetRecipe


ReferenceRenderKind = Literal[
    "lightroom_export",
    "local_approximation",
]


@dataclass(frozen=True)
class ReferenceRender:
    render_path: str
    render_sha256: str
    render_kind: ReferenceRenderKind
    color_space: str
    file_format: str
    lightroom_version: str | None
    created_from_recipe: TargetRecipe


@dataclass(frozen=True)
class ReferenceCase:
    case_id: str
    source: SourceIdentity
    recipe: TargetRecipe
    process_family: str
    camera_profile: str | None
    render: ReferenceRender | None
    status: str
