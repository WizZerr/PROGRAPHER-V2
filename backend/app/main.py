import os
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

ENGINE_SECRET = os.getenv("PROGRAPHER_ENGINE_SECRET", "")

app = FastAPI(
    title="ProGrapher Engine",
    version="0.1.0",
)


@app.middleware("http")
async def local_engine_auth(request: Request, call_next):
    # Health stays public on loopback so the desktop shell can verify startup.
    if request.url.path == "/health":
        return await call_next(request)

    supplied = request.headers.get("X-ProGrapher-Secret", "")

    if not ENGINE_SECRET or not secrets.compare_digest(supplied, ENGINE_SECRET):
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized local engine request"},
        )

    return await call_next(request)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "prographer-engine",
        "version": "0.1.0",
    }


@app.get("/api/runtime")
def runtime():
    return {
        "status": "ready",
        "service": "prographer-engine",
    }
