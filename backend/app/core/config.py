import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    engine_secret: str
    app_name: str = "ProGrapher"
    engine_version: str = "0.1.0"


def get_settings() -> Settings:
    return Settings(
        engine_secret=os.getenv("PROGRAPHER_ENGINE_SECRET", ""),
    )
