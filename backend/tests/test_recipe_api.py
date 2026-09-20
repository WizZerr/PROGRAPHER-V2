import os

from fastapi.testclient import TestClient

os.environ["PROGRAPHER_ENGINE_SECRET"] = "phase3-test-secret"

from app.application import create_app  # noqa: E402


client = TestClient(create_app())
HEADERS = {"X-ProGrapher-Secret": "phase3-test-secret"}


def test_recipe_endpoint_returns_modern_xmp_mapping() -> None:
    response = client.post(
        "/api/recipe/validate",
        headers=HEADERS,
        json={
            "process_family": "modern",
            "recipe": {
                "exposure": 5,
                "blacks": -40,
                "temperature": 5200,
                "tint": 8,
            },
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["recipe"]["exposure"] == 5.0
    assert body["recipe"]["blacks"] == -40.0
    assert body["xmp_attributes"]["Exposure2012"] == "+5.00"
    assert body["xmp_attributes"]["Blacks2012"] == "-40"


def test_recipe_endpoint_rejects_invalid_range() -> None:
    response = client.post(
        "/api/recipe/validate",
        headers=HEADERS,
        json={
            "process_family": "modern",
            "recipe": {"exposure": 6},
        },
    )

    assert response.status_code == 422
    assert "outside supported range" in response.json()["detail"]
