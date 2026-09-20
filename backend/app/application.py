from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.security import LocalEngineAuthMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="ProGrapher Engine",
        version="0.1.0",
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

    app.add_middleware(LocalEngineAuthMiddleware)
    app.include_router(api_router)

    return app
