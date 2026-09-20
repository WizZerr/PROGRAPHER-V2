from __future__ import annotations

import importlib.util
import platform
from dataclasses import dataclass


@dataclass(frozen=True)
class ComputeBackendReport:
    os: str
    architecture: str
    torch_installed: bool
    cpu_available: bool
    cuda_available: bool
    mps_available: bool
    selected_backend: str
    note: str


def _torch_capabilities() -> tuple[bool, bool, bool]:
    if importlib.util.find_spec("torch") is None:
        return False, False, False

    try:
        import torch  # type: ignore

        cuda_available = bool(torch.cuda.is_available())

        mps_backend = getattr(torch.backends, "mps", None)
        mps_available = bool(
            mps_backend
            and getattr(mps_backend, "is_available", lambda: False)()
        )

        return True, cuda_available, mps_available
    except Exception:
        # Capability detection must never make the desktop engine fail to start.
        return True, False, False


def detect_compute_backend() -> ComputeBackendReport:
    system = platform.system().lower()
    architecture = platform.machine().lower()

    torch_installed, cuda_available, mps_available = _torch_capabilities()

    if cuda_available:
        selected = "cuda"
        note = "CUDA capability detected. Model-specific accuracy still requires validation."
    elif system == "darwin" and mps_available:
        selected = "mps"
        note = "Apple MPS capability detected. Model-specific accuracy still requires validation."
    else:
        selected = "cpu"
        note = "CPU is the safe local fallback. No model-quality claim is implied."

    return ComputeBackendReport(
        os=system,
        architecture=architecture,
        torch_installed=torch_installed,
        cpu_available=True,
        cuda_available=cuda_available,
        mps_available=mps_available,
        selected_backend=selected,
        note=note,
    )
