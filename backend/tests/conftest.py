from __future__ import annotations

from collections.abc import Mapping

import pytest


@pytest.fixture(autouse=True)
def _isolate_engine_secret_per_test_module(request, monkeypatch) -> None:
    """Keep API-test auth isolated from pytest collection order.

    Several API test modules intentionally use different engine secrets. Pytest
    imports all selected modules during collection, so module-level environment
    assignments can otherwise leak between modules before tests execute.

    For modules that expose the standard HEADERS mapping, make the process
    environment match that module immediately before each test. create_app()
    then freezes the same secret that the module sends in its API requests.

    Auth lifecycle tests that do not expose HEADERS keep full control of the
    environment through their own monkeypatch setup.
    """

    headers = getattr(request.module, "HEADERS", None)
    if not isinstance(headers, Mapping):
        return

    secret = headers.get("X-ProGrapher-Secret")
    if isinstance(secret, str) and secret:
        monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", secret)
