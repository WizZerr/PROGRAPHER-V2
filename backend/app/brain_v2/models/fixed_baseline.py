from __future__ import annotations

from app.brain_v2.contracts import (
    BrainInput,
    EditRecipe,
    PredictionOrigin,
)


class FixedBaselineModel:
    """
    Wiring-only model for Phase 10.

    It is deliberately not an AI model and is never presented as quality
    output. Phase 11+ can replace this implementation through the BaseModel
    boundary.
    """

    candidate_id = "brain-v2.wiring-baseline.v1"
    candidate_version = "1"

    def predict(self, brain_input: BrainInput) -> EditRecipe:
        brain_input.validate()

        recipe = EditRecipe(
            exposure_stops=0.0,
            temperature_kelvin=None,
            tint_units=None,
            blacks_units=None,
            process_family="modern",
            process_version="11.0",
            camera_profile=None,
            origin=PredictionOrigin(
                kind="baseline",
                candidate_id=self.candidate_id,
                candidate_version=self.candidate_version,
                parent_candidate_id="baseline.train_median.v1",
            ),
            scene_context_applied=False,
            critic_checked=False,
        )
        recipe.validate()
        return recipe
