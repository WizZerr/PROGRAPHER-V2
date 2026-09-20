from fastapi.testclient import TestClient

from app.application import create_app


def test_engine_secret_is_frozen_when_app_is_created(monkeypatch) -> None:
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", "original-secret")
    app = create_app()

    # Simulate another test/process changing the environment later.
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", "different-secret")

    with TestClient(app) as client:
        accepted = client.get(
            "/api/runtime",
            headers={"X-ProGrapher-Secret": "original-secret"},
        )
        rejected = client.get(
            "/api/runtime",
            headers={"X-ProGrapher-Secret": "different-secret"},
        )

    assert accepted.status_code == 200
    assert rejected.status_code == 401
