from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.metadata import router as metadata_router
from app.api.routes.recipe import router as recipe_router
from app.api.routes.runtime import router as runtime_router
from app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(runtime_router)
api_router.include_router(metadata_router)
api_router.include_router(recipe_router)
api_router.include_router(system_router)
