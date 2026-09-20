from __future__ import annotations

from enum import StrEnum


class Responsibility(StrEnum):
    LOCAL = "local"
    REMOTE_OPTIONAL = "remote_optional"
    OUT_OF_SCOPE_FOR_LOCAL_PILOT = "out_of_scope_for_local_pilot"


LOCAL_RESPONSIBILITIES: dict[str, Responsibility] = {
    "raw_access": Responsibility.LOCAL,
    "event_index": Responsibility.LOCAL,
    "cache": Responsibility.LOCAL,
    "photographer_decisions": Responsibility.LOCAL,
    "export": Responsibility.LOCAL,
    "recipe_validation": Responsibility.LOCAL,
    "metadata_read": Responsibility.LOCAL,
}

REMOTE_OPTIONAL_RESPONSIBILITIES: dict[str, Responsibility] = {
    "account": Responsibility.REMOTE_OPTIONAL,
    "license": Responsibility.REMOTE_OPTIONAL,
    "model_download": Responsibility.REMOTE_OPTIONAL,
    "remote_training": Responsibility.REMOTE_OPTIONAL,
}

LOCAL_PILOT_EXCLUSIONS: dict[str, Responsibility] = {
    "registration": Responsibility.OUT_OF_SCOPE_FOR_LOCAL_PILOT,
    "payment": Responsibility.OUT_OF_SCOPE_FOR_LOCAL_PILOT,
}


def responsibility_map() -> dict[str, str]:
    merged = {
        **LOCAL_RESPONSIBILITIES,
        **REMOTE_OPTIONAL_RESPONSIBILITIES,
        **LOCAL_PILOT_EXCLUSIONS,
    }
    return {key: value.value for key, value in merged.items()}
