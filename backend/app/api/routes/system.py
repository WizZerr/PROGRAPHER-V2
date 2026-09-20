from fastapi import APIRouter

from app.core.execution_policy import responsibility_map
from app.schemas.system import ComputeCapabilityResponse, SystemCapabilitiesResponse
from app.services.compute_backend import detect_compute_backend

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/capabilities", response_model=SystemCapabilitiesResponse)
def get_system_capabilities() -> SystemCapabilitiesResponse:
    compute = detect_compute_backend()

    return SystemCapabilitiesResponse(
        mode="local_first",
        remote_services_enabled=False,
        responsibilities=responsibility_map(),
        compute=ComputeCapabilityResponse(
            os=compute.os,
            architecture=compute.architecture,
            torch_installed=compute.torch_installed,
            cpu_available=compute.cpu_available,
            cuda_available=compute.cuda_available,
            mps_available=compute.mps_available,
            selected_backend=compute.selected_backend,
            note=compute.note,
        ),
    )
