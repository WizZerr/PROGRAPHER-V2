from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version

from app.brain_v2.vision_encoders.contracts import EncoderRuntime


def _package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def detect_encoder_runtime() -> EncoderRuntime:
    torch_version = _package_version("torch")
    transformers_version = _package_version("transformers")
    torchvision_version = _package_version("torchvision")

    cuda_available = False
    mps_available = False
    cuda_device_name = None

    if torch_version is not None:
        try:
            torch = import_module("torch")
            cuda_available = bool(torch.cuda.is_available())
            if cuda_available:
                cuda_device_name = str(torch.cuda.get_device_name(0))

            mps_backend = getattr(
                getattr(torch, "backends", None),
                "mps",
                None,
            )
            if mps_backend is not None:
                mps_available = bool(mps_backend.is_available())
        except Exception:
            cuda_available = False
            mps_available = False
            cuda_device_name = None

    return EncoderRuntime(
        device=(
            "cuda"
            if cuda_available
            else "mps"
            if mps_available
            else "cpu"
        ),
        torch_version=torch_version,
        transformers_version=transformers_version,
        torchvision_version=torchvision_version,
        cuda_available=cuda_available,
        mps_available=mps_available,
        cuda_device_name=cuda_device_name,
    )
