from typing import Any, Literal

from pydantic import BaseModel, Field


class RecipeValidateRequest(BaseModel):
    process_family: Literal["modern", "legacy"]
    recipe: dict[str, Any] = Field(default_factory=dict)


class RecipeValidateResponse(BaseModel):
    process_family: Literal["modern", "legacy"]
    recipe: dict[str, float]
    xmp_attributes: dict[str, str]
