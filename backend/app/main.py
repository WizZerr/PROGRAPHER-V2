import os
import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

ENGINE_SECRET = os.getenv("PROGRAPHER_ENGINE_SECRET", "")

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


@app.middleware("http")
async def local_engine_auth(request: Request, call_next):
    # CORS preflight must pass through unauthenticated so CORSMiddleware
    # can validate the origin/headers and return the preflight response.
    if request.method == "OPTIONS":
        return await call_next(request)

    # Health stays public on loopback so Tauri can verify engine startup.
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
        "version": "0.1.0",
    }
