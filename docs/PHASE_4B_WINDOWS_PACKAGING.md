# ProGrapher V2 — Phase 4B Windows Packaging

## Part 1
Build and smoke-test a self-contained Python engine.

Status is only PASS after:
- PyInstaller build succeeds.
- Packaged executable starts.
- Health returns 200.
- `/api/runtime` returns 401 without the secret.
- `/api/runtime` returns 200 with the secret.
- Process can be terminated cleanly.

## Not yet complete
This does not close Phase 4B. Next steps:
- produce the final sidecar artifact,
- wire it into Tauri `externalBin`,
- build a Tauri Windows bundle,
- test on a clean Windows machine without Python/Node/Rust,
- later repeat the packaging/build pipeline on macOS Apple Silicon.
