from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


def read_env_value(key: str) -> str | None:
    direct = os.getenv(key)
    if direct is not None and direct.strip():
        return direct.strip()
    if not ENV_FILE.exists():
        return None
    for raw in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, value = line.split("=", 1)
        if k.strip() == key:
            return value.strip().strip('"').strip("'")
    return None


def resolve_data_dir() -> Path:
    configured = read_env_value("PROGRAPHER_DATA_DIR") or "./data"
    path = Path(configured)
    return (BASE_DIR / path).resolve() if not path.is_absolute() else path.resolve()


def main() -> int:
    data_dir = resolve_data_dir()
    db_path = data_dir / "prographer.db"

    print()
    print("ProGrapher Fresh Install Verification")
    print("-------------------------------------")
    print(f"Data dir: {data_dir}")
    print(f"DB:       {db_path}")
    print()

    if not db_path.exists():
        print("FAIL: prographer.db does not exist yet.")
        print("Run start_backend.bat first, wait until it is running, then try again.")
        return 2

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    checks = {
        "users": "SELECT COUNT(*) c FROM users",
        "events": "SELECT COUNT(*) c FROM events",
        "photos": "SELECT COUNT(*) c FROM photos",
        "lightroom_profile_imports": "SELECT COUNT(*) c FROM lightroom_profile_imports",
        "ai_profile_registries": "SELECT COUNT(*) c FROM ai_profile_registries",
        "ai_profile_versions": "SELECT COUNT(*) c FROM ai_profile_versions",
        "photo_ai_predictions": "SELECT COUNT(*) c FROM photo_ai_predictions",
        "ai_learning_samples": "SELECT COUNT(*) c FROM ai_learning_samples",
        "ai_retraining_runs": "SELECT COUNT(*) c FROM ai_retraining_runs",
        "event_exports": "SELECT COUNT(*) c FROM event_exports",
    }

    failed = False
    for label, sql in checks.items():
        try:
            count = int(con.execute(sql).fetchone()["c"])
        except Exception as exc:
            print(f"FAIL: {label}: schema missing or unreadable ({exc})")
            failed = True
            continue
        state = "OK" if count == 0 else "NOT EMPTY"
        print(f"{state:9} {label:28} {count}")
        if count != 0:
            failed = True

    # Core schema smoke check: a fresh backend should have these tables.
    expected_tables = {
        "users", "user_sessions", "user_onboarding", "events", "photos",
        "lightroom_profile_imports", "ai_profile_registries", "ai_profile_versions",
        "photo_ai_predictions", "ai_learning_samples", "ai_retraining_runs",
        "event_exports",
    }
    tables = {
        row["name"]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    missing = sorted(expected_tables - tables)
    if missing:
        print()
        print("FAIL: Missing expected tables:")
        for table in missing:
            print(f" - {table}")
        failed = True

    con.close()

    print()
    if failed:
        print("RESULT: NOT A CLEAN FIRST-RUN STATE")
        return 1

    print("RESULT: CLEAN FIRST-RUN STATE")
    print("Database schema exists and every product-data table checked is empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
