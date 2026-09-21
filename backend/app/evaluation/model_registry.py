from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


ModelFamily = Literal["baseline", "v1", "v2_candidate"]
CandidateStatus = Literal[
    "available",
    "missing_artifacts",
    "not_built",
    "blocked",
    "retired",
]
ChangeKind = Literal[
    "baseline",
    "correctness_fix",
    "model_experiment",
]


@dataclass(frozen=True)
class ModelDescriptor:
    candidate_id: str
    family: ModelFamily
    version: str
    status: CandidateStatus
    change_kind: ChangeKind
    description: str
    artifact_fingerprint: str | None = None
    reconstructed: bool = False
    original_user_profile: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PromotionState:
    active_candidate_id: str
    rollback_candidate_id: str | None
    quality_gate_id: str | None


def default_registry() -> tuple[ModelDescriptor, ...]:
    return (
        ModelDescriptor(
            candidate_id="baseline.train_median.v1",
            family="baseline",
            version="1",
            status="available",
            change_kind="baseline",
            description=(
                "Baseline קבוע: חציון Exposure/Temperature/Tint "
                "מדוגמאות Train מאומתות בלבד."
            ),
        ),
        ModelDescriptor(
            candidate_id="legacy.v1.clip_extratrees",
            family="v1",
            version="legacy-retired",
            status="retired",
            change_kind="model_experiment",
            description=(
                "Legacy V1 retired by product decision. "
                "Not reconstructed and not used as an active benchmark."
            ),
            artifact_fingerprint=None,
            reconstructed=False,
            original_user_profile=False,
        ),
        ModelDescriptor(
            candidate_id="v2.candidate.unbuilt",
            family="v2_candidate",
            version="0",
            status="not_built",
            change_kind="model_experiment",
            description=(
                "Placeholder למועמד V2. אין עדיין מודל ואין חיזוי."
            ),
        ),
    )


def promote_candidate(
    *,
    current: PromotionState,
    candidate_id: str,
    quality_gate_id: str | None,
    gate_passed: bool,
) -> PromotionState:
    if not gate_passed or not quality_gate_id:
        raise ValueError(
            "אי אפשר לשנות מודל ברירת מחדל בלי Quality Gate שעבר."
        )

    if candidate_id == current.active_candidate_id:
        return current

    return PromotionState(
        active_candidate_id=candidate_id,
        rollback_candidate_id=current.active_candidate_id,
        quality_gate_id=quality_gate_id,
    )
