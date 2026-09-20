# ProGrapher V2 — Phase 4B Part 1

This step freezes the FastAPI engine into a standalone Windows executable.

## Why onedir first?

PyInstaller recommends validating a one-folder bundle before moving to one-file,
because dependency problems are easier to diagnose.

## Run

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m pip freeze > requirements-lock.txt
.\.venv\Scripts\python.exe .\packaging\build_engine.py
.\.venv\Scripts\python.exe .\packaging\smoke_test_engine.py
```

Expected final output:

```text
PACKAGED_ENGINE_SMOKE_TEST_OK port=XXXXX
```

This proves the packaged engine:
- starts without invoking Python manually,
- binds only to loopback,
- passes `/health`,
- rejects unauthenticated API requests,
- accepts the per-session secret.

The next Phase 4B part will convert this into the Tauri sidecar/bundled engine.
