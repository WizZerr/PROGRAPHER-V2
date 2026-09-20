# Target System Matrix — Phase 0

| Target | Requirement | Current evidence | Status |
|---|---|---|---|
| macOS Apple Silicon arm64 | Required first release | No real-Mac execution evidence yet | NOT TESTED |
| Windows x64 | Required first release | Current code is Windows-oriented but clean target-machine evidence not recorded in this pack | NOT TESTED |
| macOS Intel x86_64 | Early feasibility / support-scope decision | No dependency/packaging evidence yet | NOT TESTED |

## Evidence to capture per machine
- Machine/model
- CPU architecture
- RAM
- OS version
- Lightroom Classic version
- Python version used for development build
- rawpy / LibRaw import + RAW decode test
- PyTorch import
- CPU inference smoke test
- MPS test on Apple Silicon where relevant
- CUDA test on supported Windows hardware where relevant
- Frontend clean install/build
- Backend clean start / health
- Unicode/Hebrew path test
- External drive test

A success on Windows does not count as a macOS test, and vice versa.
