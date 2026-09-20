import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


PUBLIC_PATHS = {"/health"}


class LocalEngineAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, engine_secret: str) -> None:
        super().__init__(app)
        self.engine_secret = engine_secret

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

        supplied = request.headers.get("X-ProGrapher-Secret", "")

        if (
            not self.engine_secret
            or not secrets.compare_digest(supplied, self.engine_secret)
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized local engine request"},
            )

        return await call_next(request)
