from __future__ import annotations

from app.brain_v2.components import QualityResult
from app.brain_v2.contracts import Availability, BrainInput, EditRecipe


class NoOpQualityControl:
    """
    Critic placeholder for the first experimental path.

    No confidence score is invented. Every output requires full review.
    """

    def evaluate(
        self,
        brain_input: BrainInput,
        recipe: EditRecipe,
    ) -> QualityResult:
        brain_input.validate()
        recipe.validate()

        result = QualityResult(
            availability=Availability(
                state="not_available",
                reason="Critic is not implemented in the first Brain V2 path.",
            ),
            requires_full_review=True,
            confidence=None,
            reason="כל תוצאה דורשת בדיקה מלאה במסלול הניסוי הראשון.",
        )
        result.validate()
        return result
