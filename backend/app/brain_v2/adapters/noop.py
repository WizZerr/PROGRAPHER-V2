from __future__ import annotations

from app.brain_v2.contracts import BrainInput, EditRecipe


class NoOpPhotographerAdapter:
    """
    Explicit placeholder until personal style data is available.
    It must not mutate or pretend to personalize the recipe.
    """

    def apply(
        self,
        brain_input: BrainInput,
        recipe: EditRecipe,
    ) -> EditRecipe:
        brain_input.validate()
        recipe.validate()
        return recipe
