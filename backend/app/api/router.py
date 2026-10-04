from fastapi import APIRouter

from app.api.routes.dataset import router as dataset_router
from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.jpeg_render import router as jpeg_render_router
from app.api.routes.jpeg_export import router as jpeg_export_router
from app.api.routes.jpeg_controls import router as jpeg_controls_router
from app.api.routes.metadata import router as metadata_router
from app.api.routes.photographer import router as photographer_router
from app.api.routes.recipe import router as recipe_router
from app.api.routes.reference import router as reference_router
from app.api.routes.runtime import router as runtime_router
from app.api.routes.system import router as system_router
from app.api.routes.testing import router as testing_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(runtime_router)
api_router.include_router(metadata_router)
api_router.include_router(recipe_router)
api_router.include_router(system_router)
api_router.include_router(events_router)
api_router.include_router(jpeg_render_router)
api_router.include_router(jpeg_export_router)
api_router.include_router(jpeg_controls_router)
api_router.include_router(photographer_router)
api_router.include_router(dataset_router)
api_router.include_router(reference_router)
api_router.include_router(testing_router)
