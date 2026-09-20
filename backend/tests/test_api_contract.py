import os

from fastapi.testclient import TestClient

os.environ["PROGRAPHER_ENGINE_SECRET"] = "phase3-test-secret"

from app.application import create_app  # noqa: E402


client = TestClient(create_app())


def test_health_is_public() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_runtime_requires_secret() -> None:
    response = client.get("/api/runtime")

    assert response.status_code == 401


def test_runtime_accepts_secret() -> None:
    response = client.get(
        "/api/runtime",
        headers={"X-ProGrapher-Secret": "phase3-test-secret"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
