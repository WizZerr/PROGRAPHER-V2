from fastapi import APIRouter, HTTPException, status

from app.domain.recipes import ProcessFamily, RecipeValidationError
from app.schemas.recipe import RecipeValidateRequest, RecipeValidateResponse
from app.services.recipe_service import recipe_to_xmp_attributes

router = APIRouter(prefix="/api/recipe", tags=["recipe"])


@router.post("/validate", response_model=RecipeValidateResponse)
def validate_recipe_contract(
    payload: RecipeValidateRequest,
) -> RecipeValidateResponse:
    family = ProcessFamily(payload.process_family)

    try:
        clean, attrs = recipe_to_xmp_attributes(payload.recipe, family)
    except RecipeValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return RecipeValidateResponse(
        process_family=family.value,
        recipe=clean,
        xmp_attributes=attrs,
    )
