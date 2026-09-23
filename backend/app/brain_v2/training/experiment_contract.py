from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.brain_v2.models.edit_targets import WhiteBalanceTargetMode
from app.brain_v2.training.dataset_manifest import DatasetImportManifest
from app.brain_v2.training.event_split import EventSafeSplitManifest


CandidateFamily = Literal[
    "simple_baseline",
    "measured_features",
    "clip",
    "dino",
    "brain",
]
TARGET_CONTRACT_VERSION = "phase12-three-target-contract-v1"
EXPERIMENT_SCHEMA_VERSION = "phase12-candidate-experiment-v1"
TARGET_NAMES = (
    "exposure_stops",
    "temperature_k",
    "tint",
)


class RepresentationSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    model_id: str | None = None
    feature_version: str | None = None

    @field_validator("name", "version")
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("representation name/version must be non-empty")
        return value


class EstimatorSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    config: dict[str, Any]

    @field_validator("name")
    @classmethod
    def require_nonempty_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("estimator name must be non-empty")
        return value


class CandidateExperimentSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = EXPERIMENT_SCHEMA_VERSION
    experiment_id: str

    candidate_name: str
    candidate_family: CandidateFamily

    dataset_id: str
    split_id: str

    target_contract_version: str = TARGET_CONTRACT_VERSION
    target_names: tuple[str, ...] = TARGET_NAMES
    white_balance_target_mode: WhiteBalanceTargetMode

    representation: RepresentationSpec
    estimator: EstimatorSpec

    random_seed: int
    code_revision: str

    train_sample_count: int
    validation_sample_count: int
    train_cohort_sha256: str
    validation_cohort_sha256: str

    @field_validator("candidate_name", "code_revision")
    @classmethod
    def require_nonempty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("candidate_name/code_revision must be non-empty")
        return value


def _hash_sample_ids(sample_ids: list[str]) -> str:
    payload = "\n".join(sorted(sample_ids)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _cohort_ids(
    split: EventSafeSplitManifest,
    split_name: Literal["train", "validation"],
) -> list[str]:
    return sorted(
        item.sample_id
        for item in split.sample_assignments
        if item.split == split_name
    )


def build_candidate_experiment_spec(
    *,
    manifest: DatasetImportManifest,
    split: EventSafeSplitManifest,
    candidate_name: str,
    candidate_family: CandidateFamily,
    white_balance_target_mode: WhiteBalanceTargetMode,
    representation: RepresentationSpec,
    estimator: EstimatorSpec,
    random_seed: int,
    code_revision: str,
) -> CandidateExperimentSpec:
    if split.dataset_id != manifest.dataset_id:
        raise ValueError(
            "split.dataset_id does not match manifest.dataset_id"
        )

    train_ids = _cohort_ids(split, "train")
    validation_ids = _cohort_ids(split, "validation")

    if not train_ids:
        raise ValueError("train cohort is empty")
    if not validation_ids:
        raise ValueError("validation cohort is empty")

    overlap = set(train_ids) & set(validation_ids)
    if overlap:
        raise ValueError(
            "sample leakage detected between train and validation: "
            + ", ".join(sorted(overlap))
        )

    manifest_ids = {
        sample.sample_id
        for sample in manifest.samples
        if sample.ready_for_three_target_training
    }
    referenced = set(train_ids) | set(validation_ids)
    missing = sorted(referenced - manifest_ids)
    if missing:
        raise ValueError(
            "split references sample IDs absent/non-ready in the manifest: "
            + ", ".join(missing)
        )

    candidate_name = candidate_name.strip()
    code_revision = code_revision.strip()
    if not candidate_name:
        raise ValueError("candidate_name must be non-empty")
    if not code_revision:
        raise ValueError("code_revision must be non-empty")

    train_hash = _hash_sample_ids(train_ids)
    validation_hash = _hash_sample_ids(validation_ids)

    identity_payload = {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "candidate_name": candidate_name,
        "candidate_family": candidate_family,
        "dataset_id": manifest.dataset_id,
        "split_id": split.split_id,
        "target_contract_version": TARGET_CONTRACT_VERSION,
        "target_names": TARGET_NAMES,
        "white_balance_target_mode": white_balance_target_mode.value,
        "representation": representation.model_dump(mode="json"),
        "estimator": estimator.model_dump(mode="json"),
        "random_seed": random_seed,
        "code_revision": code_revision,
        "train_sample_count": len(train_ids),
        "validation_sample_count": len(validation_ids),
        "train_cohort_sha256": train_hash,
        "validation_cohort_sha256": validation_hash,
    }

    experiment_id = hashlib.sha256(
        json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return CandidateExperimentSpec(
        experiment_id=experiment_id,
        candidate_name=candidate_name,
        candidate_family=candidate_family,
        dataset_id=manifest.dataset_id,
        split_id=split.split_id,
        white_balance_target_mode=white_balance_target_mode,
        representation=representation,
        estimator=estimator,
        random_seed=random_seed,
        code_revision=code_revision,
        train_sample_count=len(train_ids),
        validation_sample_count=len(validation_ids),
        train_cohort_sha256=train_hash,
        validation_cohort_sha256=validation_hash,
    )
