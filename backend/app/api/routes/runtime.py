from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/runtime")
def runtime() -> dict[str, str]:
    settings = get_settings()

    return {
        "status": "ready",
        "service": "prographer-engine",
        "version": settings.engine_version,
    }
