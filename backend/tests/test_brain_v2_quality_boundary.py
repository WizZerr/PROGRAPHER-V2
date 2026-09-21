import pytest

from app.brain_v2.components import QualityResult
from app.brain_v2.contracts import Availability


def test_unavailable_quality_cannot_report_confidence() -> None:
    result = QualityResult(
        availability=Availability(
            state="not_available",
            reason="critic not built",
        ),
        requires_full_review=True,
        confidence=0.91,
    )

    with pytest.raises(ValueError, match="confidence"):
        result.validate()


def test_unavailable_quality_requires_full_review() -> None:
    result = QualityResult(
        availability=Availability(
            state="not_available",
            reason="critic not built",
        ),
        requires_full_review=False,
        confidence=None,
    )

    with pytest.raises(ValueError, match="בדיקה מלאה"):
        result.validate()
