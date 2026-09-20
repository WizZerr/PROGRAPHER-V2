import os
import socket

from fastapi.testclient import TestClient

os.environ["PROGRAPHER_ENGINE_SECRET"] = "phase5-test-secret"

from app.application import create_app  # noqa: E402


client = TestClient(create_app())
HEADERS = {"X-ProGrapher-Secret": "phase5-test-secret"}


def test_system_capabilities_requires_secret() -> None:
    response = client.get("/api/system/capabilities")
    assert response.status_code == 401


def test_system_capabilities_reports_local_first_mode() -> None:
    response = client.get("/api/system/capabilities", headers=HEADERS)

    assert response.status_code == 200

    body = response.json()
    assert body["mode"] == "local_first"
    assert body["remote_services_enabled"] is False
    assert body["responsibilities"]["raw_access"] == "local"
    assert body["responsibilities"]["export"] == "local"
    assert body["compute"]["selected_backend"] in {"cpu", "cuda", "mps"}


def test_system_capabilities_does_not_require_network(monkeypatch) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail_network)

    response = client.get("/api/system/capabilities", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["mode"] == "local_first"
