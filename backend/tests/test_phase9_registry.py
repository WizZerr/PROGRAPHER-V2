import pytest

from app.evaluation.model_registry import (
    PromotionState,
    default_registry,
    promote_candidate,
)


def test_legacy_v1_is_retired_not_active() -> None:
    registry = default_registry()
    v1 = next(item for item in registry if item.family == "v1")

    assert v1.status == "retired"
    assert v1.reconstructed is False
    assert v1.original_user_profile is False


def test_default_change_requires_quality_gate_and_has_rollback() -> None:
    current = PromotionState(
        active_candidate_id="baseline.train_median.v1",
        rollback_candidate_id=None,
        quality_gate_id=None,
    )

    with pytest.raises(ValueError):
        promote_candidate(
            current=current,
            candidate_id="v2.candidate.001",
            quality_gate_id=None,
            gate_passed=False,
        )

    promoted = promote_candidate(
        current=current,
        candidate_id="v2.candidate.001",
        quality_gate_id="validation-gate-001",
        gate_passed=True,
    )

    assert promoted.active_candidate_id == "v2.candidate.001"
    assert promoted.rollback_candidate_id == "baseline.train_median.v1"
