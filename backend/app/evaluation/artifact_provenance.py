from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


PROVENANCE_SCHEMA = "prographer.artifact-provenance.v1"
TARGET_CONTRACT_VERSION = "jpeg-j0-target-bundle-v1"
FEATURE_CONTRACT_VERSION = "jpeg-measured-features-v1"
RENDERER_CONTRACT_VERSION = "jpeg-polynomial-rgb-renderer-v1"


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_sha256(payload: Any) -> str:
    return sha256(canonical_json_bytes(payload)).hexdigest()


def sha256_file(path: str | Path) -> str:
    source = Path(path)
    digest = sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_revision(value: str) -> str:
    candidate = value.strip()
    if candidate.startswith("git:"):
        candidate = candidate[4:]
    if not re.fullmatch(r"[0-9a-fA-F]{40}", candidate):
        raise ValueError(
            "code revision must be an exact 40-character Git commit SHA"
        )
    return "git:" + candidate.lower()


def resolve_code_revision(
    explicit: str | None = None,
    *,
    repo_root: str | Path | None = None,
) -> str:
    if explicit:
        return _normalize_revision(explicit)

    environment = os.environ.get("PROGRAPHER_CODE_REVISION")
    if environment:
        return _normalize_revision(environment)

    cwd = (
        Path(repo_root).expanduser().resolve()
        if repo_root is not None
        else Path(__file__).resolve().parents[3]
    )
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "Exact Git commit is required for artifact provenance. "
            "Run inside the repository, pass --code-revision, or set "
            "PROGRAPHER_CODE_REVISION."
        ) from exc

    return _normalize_revision(completed.stdout)


def dependency_lock_fingerprint(
    path: str | Path | None = None,
) -> dict[str, str]:
    lock_path = (
        Path(path).expanduser().resolve(strict=True)
        if path is not None
        else (
            Path(__file__).resolve().parents[2]
            / "requirements-lock.txt"
        ).resolve(strict=True)
    )
    return {
        "dependency_lock_name": lock_path.name,
        "dependency_lock_sha256": sha256_file(lock_path),
    }


def _artifact_id(prefix: str, identity_payload: dict[str, Any]) -> str:
    digest = canonical_json_sha256(identity_payload)
    return f"{prefix}-{digest[:24]}"


def target_bundle_provenance(
    *,
    dataset_snapshot_id: str,
    dataset_manifest_sha256: str,
    targets_payload_sha256: str,
    code_revision: str,
    dependency_lock_sha256: str,
    color_contract_version: str,
    recipe_contract_version: str,
    renderer_contract_version: str,
    config: dict[str, Any],
    split_mode: str,
) -> dict[str, Any]:
    identity = {
        "kind": "jpeg_j0_target_bundle",
        "target_contract_version": TARGET_CONTRACT_VERSION,
        "dataset_snapshot_id": dataset_snapshot_id,
        "dataset_manifest_sha256": dataset_manifest_sha256,
        "targets_payload_sha256": targets_payload_sha256,
        "code_revision": _normalize_revision(code_revision),
        "dependency_lock_sha256": dependency_lock_sha256,
        "color_contract_version": color_contract_version,
        "recipe_contract_version": recipe_contract_version,
        "renderer_contract_version": renderer_contract_version,
        "split_mode": split_mode,
        "config": config,
    }
    return {
        "schema": PROVENANCE_SCHEMA,
        "artifact_id": _artifact_id("targets", identity),
        "identity": identity,
    }


def candidate_provenance(
    *,
    candidate_family: str,
    model_version: str,
    dataset_snapshot_id: str,
    dataset_manifest_sha256: str,
    target_artifact_id: str,
    target_artifact_sha256: str,
    code_revision: str,
    dependency_lock_sha256: str,
    color_contract_version: str,
    feature_contract_version: str,
    feature_names: list[str],
    recipe_contract_version: str,
    renderer_contract_version: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    feature_names_sha256 = canonical_json_sha256(feature_names)
    identity = {
        "kind": "jpeg_model_candidate",
        "candidate_family": candidate_family,
        "model_version": model_version,
        "dataset_snapshot_id": dataset_snapshot_id,
        "dataset_manifest_sha256": dataset_manifest_sha256,
        "target_artifact_id": target_artifact_id,
        "target_artifact_sha256": target_artifact_sha256,
        "code_revision": _normalize_revision(code_revision),
        "dependency_lock_sha256": dependency_lock_sha256,
        "color_contract_version": color_contract_version,
        "feature_contract_version": feature_contract_version,
        "feature_names_sha256": feature_names_sha256,
        "recipe_contract_version": recipe_contract_version,
        "renderer_contract_version": renderer_contract_version,
        "config": config,
    }
    return {
        "schema": PROVENANCE_SCHEMA,
        "artifact_id": _artifact_id("candidate", identity),
        "identity": identity,
        "feature_names": feature_names,
    }


def verify_target_bundle_for_candidate(
    *,
    target_payload: dict[str, Any],
    dataset_snapshot_id: str,
    dataset_manifest_sha256: str,
) -> dict[str, Any]:
    provenance = target_payload.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError(
            "recipe targets predate immutable provenance; regenerate J0 targets"
        )
    if provenance.get("schema") != PROVENANCE_SCHEMA:
        raise ValueError("unsupported target provenance schema")

    identity = provenance.get("identity") or {}
    if identity.get("kind") != "jpeg_j0_target_bundle":
        raise ValueError("unexpected target provenance kind")
    if identity.get("dataset_snapshot_id") != dataset_snapshot_id:
        raise ValueError("target bundle belongs to a different dataset snapshot")
    if identity.get("dataset_manifest_sha256") != dataset_manifest_sha256:
        raise ValueError("target bundle belongs to a different dataset manifest")

    payload_without_provenance = dict(target_payload)
    payload_without_provenance.pop("provenance", None)
    actual_payload_sha = canonical_json_sha256(payload_without_provenance)
    if identity.get("targets_payload_sha256") != actual_payload_sha:
        raise ValueError("target bundle content hash does not match provenance")

    expected_id = _artifact_id("targets", identity)
    if provenance.get("artifact_id") != expected_id:
        raise ValueError("target artifact id does not match provenance identity")

    return provenance


def ensure_immutable_artifact_dir(
    root: str | Path,
    artifact_id: str,
) -> Path:
    path = Path(root).expanduser().resolve() / artifact_id
    if path.exists():
        raise FileExistsError(
            f"Immutable artifact already exists: {path}. "
            "Change a material input/config/version to create a new artifact id."
        )
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_immutable_json(
    path: str | Path,
    payload: dict[str, Any],
) -> None:
    destination = Path(path)
    if destination.exists():
        raise FileExistsError(
            f"Immutable artifact file already exists: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(destination)
