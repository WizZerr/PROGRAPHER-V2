from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.security import LocalEngineAuthMiddleware


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="ProGrapher Engine",
        version=settings.engine_version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=(
            r"^(http://localhost:3000|http://127\.0\.0\.1:3000|"
            r"tauri://localhost|http://tauri\.localhost|https://tauri\.localhost)$"
        ),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-ProGrapher-Secret"],
    )

    # Freeze the per-process secret when the app is created.
    # Do not reread the environment on every request.
    app.add_middleware(
        LocalEngineAuthMiddleware,
        engine_secret=settings.engine_secret,
    )

    app.include_router(api_router)

    return app
