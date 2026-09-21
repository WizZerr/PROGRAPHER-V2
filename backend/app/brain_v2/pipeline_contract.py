from __future__ import annotations

from dataclasses import dataclass

from app.brain_v2.contracts import (
    ArtifactContract,
    BrainInput,
    EditRecipe,
)


@dataclass(frozen=True)
class TrainingExample:
    brain_input: BrainInput
    target_recipe: EditRecipe
    dataset_manifest_id: str

    def validate(self) -> None:
        self.brain_input.validate()
        self.target_recipe.validate()

        if not self.dataset_manifest_id.strip():
            raise ValueError("dataset_manifest_id חסר.")


@dataclass(frozen=True)
class InferenceRequest:
    brain_input: BrainInput
    artifact: ArtifactContract

    def validate(self) -> None:
        self.artifact.validate_for_input(self.brain_input)


def validate_training_inference_contract(
    *,
    training_example: TrainingExample,
    inference_request: InferenceRequest,
) -> None:
    training_example.validate()
    inference_request.validate()

    if (
        training_example.brain_input.contract_version
        != inference_request.brain_input.contract_version
    ):
        raise ValueError(
            "Training ו-Inference משתמשים ב-Brain contract שונה."
        )

    if (
        training_example.brain_input.features.version
        != inference_request.brain_input.features.version
    ):
        raise ValueError(
            "Training ו-Inference משתמשים ב-Feature version שונה."
        )

    if (
        training_example.brain_input.preprocessing.version
        != inference_request.brain_input.preprocessing.version
    ):
        raise ValueError(
            "Training ו-Inference משתמשים ב-preprocessing version שונה."
        )
