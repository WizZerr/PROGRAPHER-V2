from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Any, Literal
from uuid import UUID
import zipfile

from packaging.version import InvalidVersion, Version


PROFILE_PACKAGE_SCHEMA = "prographer.profile-package.v1"
PROFILE_PACKAGE_MANIFEST = "profile_manifest.json"
PROFILE_PACKAGE_REQUIRED_ROLES = {"weights", "normalizer"}


class ProfilePackageError(ValueError):
    pass


class ProfilePackageCompatibilityError(ProfilePackageError):
    pass


class ProfilePackageIntegrityError(ProfilePackageError):
    pass


@dataclass(frozen=True)
class ProfileRuntimeRequirements:
    engine_version: str
    learning_source: Literal["jpeg", "raw"]
    model_contract_version: str
    feature_contract_version: str
    recipe_contract_version: str
    renderer_contract_version: str


@dataclass(frozen=True)
class BuiltProfilePackage:
    path: str
    archive_sha256: str
    manifest_sha256: str
    profile_version_id: str


@dataclass(frozen=True)
class LoadedProfilePackage:
    root: str
    archive_sha256: str
    manifest_sha256: str
    manifest: dict[str, Any]


def _canonical_json_bytes(payload: Any) -> bytes:
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProfilePackageError(
            "profile package metadata must be canonical JSON"
        ) from exc


def _sha256_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _uuid(value: str, field: str) -> str:
    try:
        parsed = UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProfilePackageError(f"{field} must be a UUID") from exc
    canonical = str(parsed)
    if str(value).lower() != canonical:
        raise ProfilePackageError(f"{field} must use canonical UUID form")
    return canonical


def _version(value: str, field: str) -> Version:
    try:
        return Version(value)
    except InvalidVersion as exc:
        raise ProfilePackageError(
            f"{field} must be a valid version"
        ) from exc


def _safe_archive_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or "\\" in value
    ):
        raise ProfilePackageIntegrityError(
            f"unsafe profile package path: {value}"
        )
    return path


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def _validate_roles(artifacts: dict[str, str | Path]) -> None:
    missing = PROFILE_PACKAGE_REQUIRED_ROLES - set(artifacts)
    if missing:
        raise ProfilePackageError(
            "profile package is missing required artifact roles: "
            + ", ".join(sorted(missing))
        )
    for role in artifacts:
        if not role or not role.replace("_", "").replace("-", "").isalnum():
            raise ProfilePackageError(f"unsafe artifact role: {role}")


def build_profile_package(
    *,
    output_path: str | Path,
    profile_id: str,
    profile_version_id: str,
    photographer_id: str,
    learning_source: Literal["jpeg", "raw"],
    version_number: int,
    artifacts: dict[str, str | Path],
    model_contract_version: str,
    feature_contract_version: str,
    recipe_contract_version: str,
    renderer_contract_version: str,
    minimum_engine_version: str,
    maximum_engine_version_exclusive: str,
    metrics: dict[str, Any],
) -> BuiltProfilePackage:
    if learning_source not in {"jpeg", "raw"}:
        raise ProfilePackageError("learning_source must be jpeg or raw")
    if isinstance(version_number, bool) or version_number < 1:
        raise ProfilePackageError("version_number must be >= 1")

    profile_id = _uuid(profile_id, "profile_id")
    profile_version_id = _uuid(
        profile_version_id,
        "profile_version_id",
    )
    photographer_id = _uuid(photographer_id, "photographer_id")

    minimum = _version(
        minimum_engine_version,
        "minimum_engine_version",
    )
    maximum = _version(
        maximum_engine_version_exclusive,
        "maximum_engine_version_exclusive",
    )
    if minimum >= maximum:
        raise ProfilePackageError(
            "engine compatibility range must be non-empty"
        )

    for field, value in {
        "model_contract_version": model_contract_version,
        "feature_contract_version": feature_contract_version,
        "recipe_contract_version": recipe_contract_version,
        "renderer_contract_version": renderer_contract_version,
    }.items():
        if not isinstance(value, str) or not value.strip():
            raise ProfilePackageError(f"{field} must be non-empty")

    _validate_roles(artifacts)

    file_entries: list[dict[str, Any]] = []
    source_files: list[tuple[str, Path]] = []

    for role in sorted(artifacts):
        source = Path(artifacts[role]).expanduser().resolve(strict=True)
        if not source.is_file():
            raise ProfilePackageError(
                f"artifact is not a file: {source}"
            )
        archive_path = (
            PurePosixPath("artifacts")
            / role
            / source.name
        ).as_posix()
        _safe_archive_path(archive_path)
        payload_sha = _sha256_file(source)
        size = source.stat().st_size
        file_entries.append(
            {
                "role": role,
                "path": archive_path,
                "sha256": payload_sha,
                "size_bytes": int(size),
            }
        )
        source_files.append((archive_path, source))

    manifest = {
        "schema": PROFILE_PACKAGE_SCHEMA,
        "profile_id": profile_id,
        "profile_version_id": profile_version_id,
        "photographer_id": photographer_id,
        "version_number": int(version_number),
        "learning_source": learning_source,
        "contracts": {
            "model": model_contract_version,
            "feature": feature_contract_version,
            "recipe": recipe_contract_version,
            "renderer": renderer_contract_version,
        },
        "engine_compatibility": {
            "minimum": str(minimum),
            "maximum_exclusive": str(maximum),
        },
        "metrics": metrics,
        "files": file_entries,
    }
    manifest_bytes = _canonical_json_bytes(manifest)
    manifest_sha = _sha256_bytes(manifest_bytes)

    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ProfilePackageError(
            "profile package output already exists"
        )

    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )
    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            archive.writestr(
                _zip_info(PROFILE_PACKAGE_MANIFEST),
                manifest_bytes,
            )
            for archive_path, source in source_files:
                archive.writestr(
                    _zip_info(archive_path),
                    source.read_bytes(),
                )
        os.replace(temporary, destination)
    except OSError as exc:
        raise ProfilePackageError(
            f"failed to write profile package: {exc}"
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)

    return BuiltProfilePackage(
        path=str(destination),
        archive_sha256=_sha256_file(destination),
        manifest_sha256=manifest_sha,
        profile_version_id=profile_version_id,
    )


def _read_manifest(
    archive: zipfile.ZipFile,
) -> tuple[dict[str, Any], bytes]:
    try:
        payload = archive.read(PROFILE_PACKAGE_MANIFEST)
    except KeyError as exc:
        raise ProfilePackageIntegrityError(
            "profile package manifest is missing"
        ) from exc

    try:
        manifest = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProfilePackageIntegrityError(
            "profile package manifest is invalid JSON"
        ) from exc
    if not isinstance(manifest, dict):
        raise ProfilePackageIntegrityError(
            "profile package manifest must be an object"
        )
    if manifest.get("schema") != PROFILE_PACKAGE_SCHEMA:
        raise ProfilePackageIntegrityError(
            "unsupported profile package schema"
        )
    return manifest, payload


def _validate_archive_members(
    archive: zipfile.ZipFile,
    manifest: dict[str, Any],
) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    names: dict[str, zipfile.ZipInfo] = {}
    for info in infos:
        name = info.filename
        _safe_archive_path(name)
        if name in names:
            raise ProfilePackageIntegrityError(
                f"duplicate package member: {name}"
            )
        file_type = (info.external_attr >> 16) & 0o170000
        if file_type == 0o120000:
            raise ProfilePackageIntegrityError(
                f"symlink package member is not allowed: {name}"
            )
        names[name] = info

    files = manifest.get("files")
    if not isinstance(files, list):
        raise ProfilePackageIntegrityError(
            "profile package files list is missing"
        )

    expected = {PROFILE_PACKAGE_MANIFEST}
    roles: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ProfilePackageIntegrityError(
                "invalid profile package file record"
            )
        role = item.get("role")
        path = item.get("path")
        if not isinstance(role, str) or not isinstance(path, str):
            raise ProfilePackageIntegrityError(
                "profile package file role/path is invalid"
            )
        if role in roles:
            raise ProfilePackageIntegrityError(
                f"duplicate artifact role: {role}"
            )
        roles.add(role)
        _safe_archive_path(path)
        expected.add(path)

    missing_roles = PROFILE_PACKAGE_REQUIRED_ROLES - roles
    if missing_roles:
        raise ProfilePackageIntegrityError(
            "profile package required roles are missing"
        )
    if set(names) != expected:
        raise ProfilePackageIntegrityError(
            "profile package members do not match manifest"
        )
    return names


def _check_compatibility(
    manifest: dict[str, Any],
    runtime: ProfileRuntimeRequirements,
) -> None:
    if manifest.get("learning_source") != runtime.learning_source:
        raise ProfilePackageCompatibilityError(
            "profile learning source is incompatible"
        )

    contracts = manifest.get("contracts")
    if not isinstance(contracts, dict):
        raise ProfilePackageIntegrityError(
            "profile package contracts are missing"
        )

    expected_contracts = {
        "model": runtime.model_contract_version,
        "feature": runtime.feature_contract_version,
        "recipe": runtime.recipe_contract_version,
        "renderer": runtime.renderer_contract_version,
    }
    for key, expected in expected_contracts.items():
        if contracts.get(key) != expected:
            raise ProfilePackageCompatibilityError(
                f"profile {key} contract is incompatible"
            )

    compatibility = manifest.get("engine_compatibility")
    if not isinstance(compatibility, dict):
        raise ProfilePackageIntegrityError(
            "profile engine compatibility is missing"
        )
    engine = _version(runtime.engine_version, "engine_version")
    minimum = _version(
        str(compatibility.get("minimum") or ""),
        "minimum_engine_version",
    )
    maximum = _version(
        str(compatibility.get("maximum_exclusive") or ""),
        "maximum_engine_version_exclusive",
    )
    if not minimum <= engine < maximum:
        raise ProfilePackageCompatibilityError(
            "profile package is incompatible with this engine version"
        )


def load_profile_package(
    *,
    package_path: str | Path,
    destination_root: str | Path,
    runtime: ProfileRuntimeRequirements,
) -> LoadedProfilePackage:
    package = Path(package_path).expanduser().resolve(strict=True)
    if not package.is_file():
        raise ProfilePackageError("profile package is not a file")

    archive_sha = _sha256_file(package)
    destination_base = Path(destination_root).expanduser().resolve()
    destination_base.mkdir(parents=True, exist_ok=True)

    try:
        archive = zipfile.ZipFile(package, mode="r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProfilePackageIntegrityError(
            "profile package is not a valid ZIP archive"
        ) from exc

    with archive:
        manifest, manifest_bytes = _read_manifest(archive)
        profile_version_id = _uuid(
            str(manifest.get("profile_version_id") or ""),
            "profile_version_id",
        )
        _uuid(str(manifest.get("profile_id") or ""), "profile_id")
        _uuid(
            str(manifest.get("photographer_id") or ""),
            "photographer_id",
        )
        _check_compatibility(manifest, runtime)
        members = _validate_archive_members(archive, manifest)

        final_root = destination_base / profile_version_id
        if final_root.exists():
            raise ProfilePackageError(
                "immutable profile version already exists locally"
            )

        temporary_root = Path(
            tempfile.mkdtemp(
                prefix=".profile-import-",
                dir=str(destination_base),
            )
        )
        try:
            for item in manifest["files"]:
                archive_path = item["path"]
                info = members[archive_path]
                payload = archive.read(info)
                if len(payload) != int(item.get("size_bytes") or -1):
                    raise ProfilePackageIntegrityError(
                        f"profile artifact size mismatch: {archive_path}"
                    )
                if _sha256_bytes(payload) != item.get("sha256"):
                    raise ProfilePackageIntegrityError(
                        f"profile artifact hash mismatch: {archive_path}"
                    )

                relative = _safe_archive_path(archive_path)
                destination = temporary_root.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(payload)

            normalized_manifest = _canonical_json_bytes(manifest)
            if normalized_manifest != manifest_bytes:
                raise ProfilePackageIntegrityError(
                    "profile manifest is not canonical"
                )
            (temporary_root / PROFILE_PACKAGE_MANIFEST).write_bytes(
                manifest_bytes
            )
            os.replace(temporary_root, final_root)
        except Exception:
            shutil.rmtree(temporary_root, ignore_errors=True)
            raise

    return LoadedProfilePackage(
        root=str(final_root),
        archive_sha256=archive_sha,
        manifest_sha256=_sha256_bytes(manifest_bytes),
        manifest=manifest,
    )
