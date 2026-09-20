from pydantic import BaseModel


class ComputeCapabilityResponse(BaseModel):
    os: str
    architecture: str
    torch_installed: bool
    cpu_available: bool
    cuda_available: bool
    mps_available: bool
    selected_backend: str
    note: str


class SystemCapabilitiesResponse(BaseModel):
    mode: str
    remote_services_enabled: bool
    responsibilities: dict[str, str]
    compute: ComputeCapabilityResponse
