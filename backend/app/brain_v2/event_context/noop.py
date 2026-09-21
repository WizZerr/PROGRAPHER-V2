from __future__ import annotations

from app.brain_v2.contracts import BrainInput, EditRecipe


class NoOpEventContext:
    """
    Explicit first-path placeholder.
    Event Context remains unavailable and must not alter the recipe.
    """

    def apply(
        self,
        brain_input: BrainInput,
        recipe: EditRecipe,
    ) -> EditRecipe:
        brain_input.validate()
        recipe.validate()

        if brain_input.scene_context.state != "not_available":
            raise ValueError(
                "NoOpEventContext מיועד רק למסלול שבו Scene Context לא זמין."
            )

        return recipe
