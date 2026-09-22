from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


EncoderFamily = Literal["measured", "clip", "dinov3"]
EncoderStatus = Literal["available", "optional_dependency", "blocked"]
RuntimeDevice = Literal["cpu", "cuda", "mps"]


@dataclass(frozen=True)
class EncoderDescriptor:
    encoder_id: str
    family: EncoderFamily
    version: str
    status: EncoderStatus
    model_id: str | None
    embedding_source: str
    license_status: str
    notes: str

    def validate(self) -> None:
        if not self.encoder_id.strip():
            raise ValueError("encoder_id חסר.")
        if not self.version.strip():
            raise ValueError("encoder version חסרה.")
        if self.family != "measured" and not self.model_id:
            raise ValueError("Vision model candidate חייב model_id.")

    def to_dict(self) -> dict:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class EncoderRuntime:
    device: RuntimeDevice
    torch_version: str | None
    transformers_version: str | None
    torchvision_version: str | None
    cuda_available: bool
    mps_available: bool
    cuda_device_name: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EncoderResult:
    encoder_id: str
    encoder_version: str
    vector: tuple[float, ...]
    dimension: int
    device: RuntimeDevice
    input_contract: str

    def validate(self) -> None:
        if not self.encoder_id.strip():
            raise ValueError("encoder_id חסר.")
        if not self.encoder_version.strip():
            raise ValueError("encoder_version חסרה.")
        if self.dimension <= 0:
            raise ValueError("embedding dimension חייב להיות חיובי.")
        if self.dimension != len(self.vector):
            raise ValueError(
                "embedding dimension אינו תואם לאורך vector."
            )
        if not self.input_contract.strip():
            raise ValueError("input_contract חסר.")
