from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
EXE_NAME = "prographer-engine.exe" if sys.platform == "win32" else "prographer-engine"
ENGINE_EXE = BACKEND_DIR / "dist" / "prographer-engine" / EXE_NAME


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request(url: str, secret: str | None = None) -> tuple[int, dict]:
    headers = {}
    if secret:
        headers["X-ProGrapher-Secret"] = secret

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read().decode("utf-8"))
        return exc.code, body


def wait_for_health(port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/health"

    while time.monotonic() < deadline:
        try:
            status, body = request(url)
            if status == 200 and body.get("status") == "ok":
                return
        except Exception:
            pass
        time.sleep(0.15)

    raise RuntimeError("Packaged engine did not become healthy in time.")


def main() -> None:
    if not ENGINE_EXE.exists():
        raise SystemExit(
            "Packaged engine not found. Run packaging/build_engine.py first."
        )

    port = free_port()
    secret = secrets.token_urlsafe(32)
    env = os.environ.copy()
    env["PROGRAPHER_ENGINE_SECRET"] = secret

    process = subprocess.Popen(
        [
            str(ENGINE_EXE),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ENGINE_EXE.parent,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        wait_for_health(port)

        status, health = request(f"http://127.0.0.1:{port}/health")
        assert status == 200
        assert health["status"] == "ok"

        status, _ = request(f"http://127.0.0.1:{port}/api/runtime")
        assert status == 401

        status, runtime = request(
            f"http://127.0.0.1:{port}/api/runtime",
            secret=secret,
        )
        assert status == 200
        assert runtime["status"] == "ready"

        print(f"PACKAGED_ENGINE_SMOKE_TEST_OK port={port}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
