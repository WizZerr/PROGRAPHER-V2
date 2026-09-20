import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings


PUBLIC_PATHS = {"/health"}


class LocalEngineAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # CORS preflight must reach CORSMiddleware.
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        settings = get_settings()
        supplied = request.headers.get("X-ProGrapher-Secret", "")

        if (
            not settings.engine_secret
            or not secrets.compare_digest(supplied, settings.engine_secret)
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized local engine request"},
            )

        return await call_next(request)
