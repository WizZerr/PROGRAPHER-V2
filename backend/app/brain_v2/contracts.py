from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


BRAIN_CONTRACT_VERSION = "2.0.0"

ProcessFamily = Literal["modern", "legacy", "unknown"]
AvailabilityState = Literal["available", "not_available"]
PredictionOriginKind = Literal[
    "baseline",
    "base_model",
    "photographer_adapter",
    "event_context",
    "manual",
]


@dataclass(frozen=True)
class Availability:
    state: AvailabilityState
    reason: str | None = None

    def validate(self) -> None:
        if self.state == "not_available" and not self.reason:
            raise ValueError(
                "רכיב לא זמין חייב לכלול reason מפורש."
            )

        if self.state == "available" and self.reason:
            raise ValueError(
                "רכיב זמין לא אמור לכלול reason."
            )


@dataclass(frozen=True)
class CameraInfo:
    make: str | None = None
    model: str | None = None
    serial: str | None = None


@dataclass(frozen=True)
class PreprocessingInfo:
    version: str
    raw_decoder: str
    color_pipeline: str
    preview_max_edge_px: int | None = None

    def validate(self) -> None:
        if not self.version.strip():
            raise ValueError("preprocessing.version חסר.")
        if not self.raw_decoder.strip():
            raise ValueError("raw_decoder חסר.")
        if not self.color_pipeline.strip():
            raise ValueError("color_pipeline חסר.")
        if (
            self.preview_max_edge_px is not None
            and self.preview_max_edge_px <= 0
        ):
            raise ValueError("preview_max_edge_px חייב להיות חיובי.")


@dataclass(frozen=True)
class FeatureVector:
    version: str
    values: tuple[float, ...]
    feature_names: tuple[str, ...]

    def validate(self) -> None:
        if not self.version.strip():
            raise ValueError("Feature version חסרה.")
        if len(self.values) != len(self.feature_names):
            raise ValueError(
                "מספר ערכי Features אינו תואם למספר השמות."
            )
        if len(set(self.feature_names)) != len(self.feature_names):
            raise ValueError("Feature names מכילים כפילויות.")


@dataclass(frozen=True)
class BrainInput:
    source_fingerprint: str
    event_id: str
    camera: CameraInfo
    captured_at: str | None
    raw_wb: tuple[float, ...] | None
    exif: dict[str, float | int | str | None]
    missing_fields: tuple[str, ...]
    preprocessing: PreprocessingInfo
    features: FeatureVector
    scene_context: Availability
    critic: Availability
    contract_version: str = BRAIN_CONTRACT_VERSION

    def validate(self) -> None:
        if self.contract_version != BRAIN_CONTRACT_VERSION:
            raise ValueError(
                "BrainInput contract version אינו נתמך."
            )

        if not self.source_fingerprint.strip():
            raise ValueError("source_fingerprint חסר.")

        if not self.event_id.strip():
            raise ValueError("event_id חסר.")

        self.preprocessing.validate()
        self.features.validate()
        self.scene_context.validate()
        self.critic.validate()

        if self.raw_wb is None and "raw_wb" not in self.missing_fields:
            raise ValueError(
                "RAW WB חסר חייב להופיע ב-missing_fields."
            )

        if self.camera.model is None and "camera_model" not in self.missing_fields:
            raise ValueError(
                "Camera model חסר חייב להופיע ב-missing_fields."
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BrainInput":
        camera = CameraInfo(**payload["camera"])
        preprocessing = PreprocessingInfo(**payload["preprocessing"])
        features_payload = payload["features"]
        features = FeatureVector(
            version=features_payload["version"],
            values=tuple(features_payload["values"]),
            feature_names=tuple(features_payload["feature_names"]),
        )
        scene_context = Availability(**payload["scene_context"])
        critic = Availability(**payload["critic"])

        instance = cls(
            source_fingerprint=payload["source_fingerprint"],
            event_id=payload["event_id"],
            camera=camera,
            captured_at=payload.get("captured_at"),
            raw_wb=(
                tuple(payload["raw_wb"])
                if payload.get("raw_wb") is not None
                else None
            ),
            exif=dict(payload.get("exif") or {}),
            missing_fields=tuple(payload.get("missing_fields") or ()),
            preprocessing=preprocessing,
            features=features,
            scene_context=scene_context,
            critic=critic,
            contract_version=payload.get(
                "contract_version",
                BRAIN_CONTRACT_VERSION,
            ),
        )
        instance.validate()
        return instance


@dataclass(frozen=True)
class PredictionOrigin:
    kind: PredictionOriginKind
    candidate_id: str
    candidate_version: str
    profile_id: str | None = None
    profile_version: str | None = None
    parent_candidate_id: str | None = None

    def validate(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id חסר.")
        if not self.candidate_version.strip():
            raise ValueError("candidate_version חסרה.")
        if self.profile_id and not self.profile_version:
            raise ValueError(
                "profile_id מחייב profile_version."
            )


@dataclass(frozen=True)
class EditRecipe:
    exposure_stops: float | None
    temperature_kelvin: int | None
    tint_units: int | None
    blacks_units: float | None
    process_family: ProcessFamily
    process_version: str | None
    camera_profile: str | None
    origin: PredictionOrigin
    scene_context_applied: bool
    critic_checked: bool
    contract_version: str = BRAIN_CONTRACT_VERSION

    def validate(self) -> None:
        if self.contract_version != BRAIN_CONTRACT_VERSION:
            raise ValueError(
                "EditRecipe contract version אינו נתמך."
            )

        if not -5.0 <= (self.exposure_stops or 0.0) <= 5.0:
            raise ValueError(
                "Exposure חייב להיות בטווח ±5 stops."
            )

        if (
            self.temperature_kelvin is not None
            and not 1500 <= self.temperature_kelvin <= 50000
        ):
            raise ValueError(
                "Temperature מחוץ לטווח Kelvin נתמך."
            )

        if (
            self.tint_units is not None
            and not -150 <= self.tint_units <= 150
        ):
            raise ValueError(
                "Tint מחוץ לטווח הנתמך."
            )

        if (
            self.blacks_units is not None
            and not -100.0 <= self.blacks_units <= 100.0
        ):
            raise ValueError(
                "Blacks מחוץ לטווח הנתמך."
            )

        self.origin.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EditRecipe":
        origin = PredictionOrigin(**payload["origin"])
        instance = cls(
            exposure_stops=payload.get("exposure_stops"),
            temperature_kelvin=payload.get("temperature_kelvin"),
            tint_units=payload.get("tint_units"),
            blacks_units=payload.get("blacks_units"),
            process_family=payload["process_family"],
            process_version=payload.get("process_version"),
            camera_profile=payload.get("camera_profile"),
            origin=origin,
            scene_context_applied=bool(
                payload.get("scene_context_applied", False)
            ),
            critic_checked=bool(
                payload.get("critic_checked", False)
            ),
            contract_version=payload.get(
                "contract_version",
                BRAIN_CONTRACT_VERSION,
            ),
        )
        instance.validate()
        return instance


@dataclass(frozen=True)
class ArtifactContract:
    artifact_id: str
    candidate_id: str
    candidate_version: str
    parent_candidate_id: str | None
    brain_contract_version: str
    preprocessing_version: str
    feature_version: str
    dataset_manifest_id: str
    software_version: str
    profile_schema_version: str | None = None

    def validate_for_input(self, brain_input: BrainInput) -> None:
        brain_input.validate()

        if self.brain_contract_version != brain_input.contract_version:
            raise ValueError(
                "Model artifact אינו תואם לגרסת Brain contract."
            )

        if self.preprocessing_version != brain_input.preprocessing.version:
            raise ValueError(
                "Model artifact אינו תואם לגרסת preprocessing."
            )

        if self.feature_version != brain_input.features.version:
            raise ValueError(
                "Model artifact אינו תואם לגרסת Features."
            )

        if not self.dataset_manifest_id.strip():
            raise ValueError(
                "Model artifact חסר dataset_manifest_id."
            )
