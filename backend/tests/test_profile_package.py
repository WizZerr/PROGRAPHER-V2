from __future__ import annotations

from pathlib import Path
import shutil
from uuid import uuid4
import zipfile

import pytest

from app.profiles.package import (
    ProfilePackageCompatibilityError,
    ProfilePackageError,
    ProfilePackageIntegrityError,
    ProfileRuntimeRequirements,
    build_profile_package,
    load_profile_package,
)


def _ids():
    return str(uuid4()), str(uuid4()), str(uuid4())


def _artifacts(tmp_path: Path) -> dict[str, Path]:
    weights = tmp_path / "model.npz"
    normalizer = tmp_path / "normalizer.json"
    weights.write_bytes(b"model-weights-v1")
    normalizer.write_text(
        '{"mean":[0.1,0.2],"std":[1.0,1.1]}',
        encoding="utf-8",
    )
    return {
        "weights": weights,
        "normalizer": normalizer,
    }


def _runtime(renderer: str = "renderer-v1"):
    return ProfileRuntimeRequirements(
        engine_version="0.1.0",
        learning_source="jpeg",
        model_contract_version="model-v1",
        feature_contract_version="features-v1",
        recipe_contract_version="recipe-v1",
        renderer_contract_version=renderer,
    )


def _build(tmp_path: Path):
    profile_id, version_id, photographer_id = _ids()
    package = tmp_path / "profile.pgprofile"
    result = build_profile_package(
        output_path=package,
        profile_id=profile_id,
        profile_version_id=version_id,
        photographer_id=photographer_id,
        learning_source="jpeg",
        version_number=1,
        artifacts=_artifacts(tmp_path),
        model_contract_version="model-v1",
        feature_contract_version="features-v1",
        recipe_contract_version="recipe-v1",
        renderer_contract_version="renderer-v1",
        minimum_engine_version="0.1.0",
        maximum_engine_version_exclusive="0.2.0",
        metrics={"validation_mae": 0.12},
    )
    return result, version_id


def test_package_loads_after_being_moved(tmp_path: Path) -> None:
    built, version_id = _build(tmp_path)
    moved = tmp_path / "moved" / "renamed.pgprofile"
    moved.parent.mkdir()
    shutil.copy2(built.path, moved)

    loaded = load_profile_package(
        package_path=moved,
        destination_root=tmp_path / "cache",
        runtime=_runtime(),
    )

    root = Path(loaded.root)
    assert root.name == version_id
    assert (root / "profile_manifest.json").is_file()
    assert (root / "artifacts" / "weights" / "model.npz").read_bytes() == (
        b"model-weights-v1"
    )
    assert loaded.archive_sha256
    assert loaded.manifest_sha256


def test_incompatible_renderer_is_rejected_without_partial_install(
    tmp_path: Path,
) -> None:
    built, version_id = _build(tmp_path)
    cache = tmp_path / "cache"

    with pytest.raises(ProfilePackageCompatibilityError):
        load_profile_package(
            package_path=built.path,
            destination_root=cache,
            runtime=_runtime(renderer="renderer-v2"),
        )

    assert not (cache / version_id).exists()


def test_incompatible_engine_is_rejected_without_partial_install(
    tmp_path: Path,
) -> None:
    built, version_id = _build(tmp_path)
    cache = tmp_path / "cache"
    runtime = _runtime()
    runtime = ProfileRuntimeRequirements(
        engine_version="0.2.0",
        learning_source=runtime.learning_source,
        model_contract_version=runtime.model_contract_version,
        feature_contract_version=runtime.feature_contract_version,
        recipe_contract_version=runtime.recipe_contract_version,
        renderer_contract_version=runtime.renderer_contract_version,
    )

    with pytest.raises(ProfilePackageCompatibilityError):
        load_profile_package(
            package_path=built.path,
            destination_root=cache,
            runtime=runtime,
        )

    assert not (cache / version_id).exists()


def test_tampered_artifact_is_rejected(tmp_path: Path) -> None:
    built, version_id = _build(tmp_path)
    tampered = tmp_path / "tampered.pgprofile"

    with zipfile.ZipFile(built.path, "r") as source:
        records = {
            info.filename: source.read(info)
            for info in source.infolist()
        }
    records["artifacts/weights/model.npz"] = b"tampered"

    with zipfile.ZipFile(tampered, "w") as output:
        for name, payload in records.items():
            output.writestr(name, payload)

    cache = tmp_path / "cache"
    with pytest.raises(ProfilePackageIntegrityError):
        load_profile_package(
            package_path=tampered,
            destination_root=cache,
            runtime=_runtime(),
        )

    assert not (cache / version_id).exists()


def test_required_weights_and_normalizer_roles_are_enforced(
    tmp_path: Path,
) -> None:
    profile_id, version_id, photographer_id = _ids()
    weights = tmp_path / "model.npz"
    weights.write_bytes(b"weights")

    with pytest.raises(ProfilePackageError, match="normalizer"):
        build_profile_package(
            output_path=tmp_path / "bad.pgprofile",
            profile_id=profile_id,
            profile_version_id=version_id,
            photographer_id=photographer_id,
            learning_source="jpeg",
            version_number=1,
            artifacts={"weights": weights},
            model_contract_version="model-v1",
            feature_contract_version="features-v1",
            recipe_contract_version="recipe-v1",
            renderer_contract_version="renderer-v1",
            minimum_engine_version="0.1.0",
            maximum_engine_version_exclusive="0.2.0",
            metrics={},
        )


def test_existing_profile_version_is_immutable(tmp_path: Path) -> None:
    built, _ = _build(tmp_path)
    cache = tmp_path / "cache"

    load_profile_package(
        package_path=built.path,
        destination_root=cache,
        runtime=_runtime(),
    )

    with pytest.raises(ProfilePackageError, match="already exists"):
        load_profile_package(
            package_path=built.path,
            destination_root=cache,
            runtime=_runtime(),
        )



def test_registry_archive_hash_mismatch_is_rejected_before_install(
    tmp_path: Path,
) -> None:
    built, version_id = _build(tmp_path)
    cache = tmp_path / "cache"

    with pytest.raises(
        ProfilePackageIntegrityError,
        match="registry",
    ):
        load_profile_package(
            package_path=built.path,
            destination_root=cache,
            runtime=_runtime(),
            expected_archive_sha256="0" * 64,
        )

    assert not (cache / version_id).exists()


def test_non_integer_version_number_is_rejected(tmp_path: Path) -> None:
    profile_id, version_id, photographer_id = _ids()

    with pytest.raises(ProfilePackageError, match="positive integer"):
        build_profile_package(
            output_path=tmp_path / "bad-version.pgprofile",
            profile_id=profile_id,
            profile_version_id=version_id,
            photographer_id=photographer_id,
            learning_source="jpeg",
            version_number=1.5,
            artifacts=_artifacts(tmp_path),
            model_contract_version="model-v1",
            feature_contract_version="features-v1",
            recipe_contract_version="recipe-v1",
            renderer_contract_version="renderer-v1",
            minimum_engine_version="0.1.0",
            maximum_engine_version_exclusive="0.2.0",
            metrics={},
        )
