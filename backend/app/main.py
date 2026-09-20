from fastapi import FastAPI

app = FastAPI(
    title="ProGrapher Engine",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "prographer-engine",
        "version": "0.1.0",
    }