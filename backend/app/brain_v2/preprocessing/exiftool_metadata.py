from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Literal, Protocol

from app.brain_v2.components import RawInputRecord


CameraMetadataState = Literal["available", "unavailable", "error"]


@dataclass(frozen=True)
class CameraMetadataResult:
    state: CameraMetadataState
    provider_id: str
    make: str | None = None
    model: str | None = None
    lens_model: str | None = None
    captured_at: str | None = None
    reason: str | None = None

    @property
    def available(self) -> bool:
        return self.state == "available"


class CameraMetadataProvider(Protocol):
    def read(self, raw_path: str | Path) -> CameraMetadataResult:
        ...


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


class ExifToolMetadataProvider:
    PROVIDER_ID = "exiftool-cli-v1"

    def __init__(
        self,
        *,
        executable: str | Path | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._explicit_executable = Path(executable) if executable is not None else None
        self.timeout_seconds = float(timeout_seconds)

    def resolve_executable(self) -> Path | None:
        if self._explicit_executable is not None:
            candidate = self._explicit_executable.expanduser().resolve()
            return candidate if candidate.is_file() else None

        env_value = os.environ.get("PROGRAPHER_EXIFTOOL_PATH")
        if env_value:
            candidate = Path(env_value).expanduser().resolve()
            if candidate.is_file():
                return candidate

        backend_root = Path(__file__).resolve().parents[3]
        for name in ("exiftool.exe", "exiftool"):
            candidate = backend_root / "vendor" / "exiftool" / name
            if candidate.is_file():
                return candidate

        for command in ("exiftool", "exiftool.exe"):
            located = shutil.which(command)
            if located:
                candidate = Path(located).resolve()
                if candidate.is_file():
                    return candidate

        return None

    def read(self, raw_path: str | Path) -> CameraMetadataResult:
        source = Path(raw_path)
        if not source.is_file():
            return CameraMetadataResult(
                state="unavailable",
                provider_id=self.PROVIDER_ID,
                reason="source_file_not_found",
            )

        executable = self.resolve_executable()
        if executable is None:
            return CameraMetadataResult(
                state="unavailable",
                provider_id=self.PROVIDER_ID,
                reason="exiftool_executable_not_found",
            )

        try:
            completed = subprocess.run(
                [
                    str(executable),
                    "-j",
                    "-Make",
                    "-Model",
                    "-LensModel",
                    "-DateTimeOriginal",
                    str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                check=False,
            )
        except Exception as exc:
            return CameraMetadataResult(
                state="error",
                provider_id=self.PROVIDER_ID,
                reason=f"{type(exc).__name__}: {exc}",
            )

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            return CameraMetadataResult(
                state="error",
                provider_id=self.PROVIDER_ID,
                reason=f"return_code={completed.returncode}: {detail}",
            )

        try:
            payload = json.loads(completed.stdout)
            row = payload[0] if isinstance(payload, list) and payload else {}
            if not isinstance(row, dict):
                raise ValueError("ExifTool JSON root did not contain an object.")
        except Exception as exc:
            return CameraMetadataResult(
                state="error",
                provider_id=self.PROVIDER_ID,
                reason=f"invalid_json: {type(exc).__name__}: {exc}",
            )

        make = _clean(row.get("Make"))
        model = _clean(row.get("Model"))
        lens_model = _clean(row.get("LensModel"))
        captured_at = _clean(row.get("DateTimeOriginal"))

        if not any((make, model, lens_model, captured_at)):
            return CameraMetadataResult(
                state="unavailable",
                provider_id=self.PROVIDER_ID,
                reason="requested_metadata_not_present",
            )

        return CameraMetadataResult(
            state="available",
            provider_id=self.PROVIDER_ID,
            make=make,
            model=model,
            lens_model=lens_model,
            captured_at=captured_at,
        )


def enrich_raw_input_with_camera_metadata(
    raw: RawInputRecord,
    metadata: CameraMetadataResult,
) -> RawInputRecord:
    if not metadata.available:
        return raw

    recovered_fields: set[str] = set()

    make = raw.camera.make
    if not make and metadata.make:
        make = metadata.make
        recovered_fields.add("camera_make")

    model = raw.camera.model
    if not model and metadata.model:
        model = metadata.model
        recovered_fields.add("camera_model")

    captured_at = raw.captured_at
    if captured_at is None and metadata.captured_at:
        captured_at = metadata.captured_at
        recovered_fields.add("captured_at")

    exif = dict(raw.exif)
    if metadata.lens_model and not _clean(exif.get("lens_model")):
        exif["lens_model"] = metadata.lens_model

    camera = replace(
        raw.camera,
        make=make,
        model=model,
    )

    missing_fields = tuple(
        field
        for field in raw.missing_fields
        if field not in recovered_fields
    )

    return replace(
        raw,
        camera=camera,
        captured_at=captured_at,
        exif=exif,
        missing_fields=missing_fields,
    )
