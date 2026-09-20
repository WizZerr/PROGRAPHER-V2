from __future__ import annotations

import argparse
import os

import uvicorn

from app.application import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ProGrapher local engine")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("ProGrapher Engine may only bind to loopback.")

    if not os.getenv("PROGRAPHER_ENGINE_SECRET"):
        raise SystemExit("PROGRAPHER_ENGINE_SECRET is required.")

    uvicorn.run(
        create_app(),
        host="127.0.0.1",
        port=args.port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
