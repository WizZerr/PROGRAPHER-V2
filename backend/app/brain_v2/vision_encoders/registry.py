from __future__ import annotations

from app.brain_v2.vision_encoders.contracts import EncoderDescriptor


SIMPLE_MEASURED_ID = "measured.unified-features.v1"
CLIP_VIT_B32_ID = "clip.openai-vit-b32.v1"
DINOV3_VITS16_ID = "dinov3.vits16-lvd1689m.v1"


def encoder_registry() -> tuple[EncoderDescriptor, ...]:
    items = (
        EncoderDescriptor(
            encoder_id=SIMPLE_MEASURED_ID,
            family="measured",
            version="1",
            status="available",
            model_id=None,
            embedding_source=(
                "BrainInput.features numeric vector "
                "(brain-v2-features-v1.2)"
            ),
            license_status="project-owned feature code",
            notes="Control candidate. No pretrained vision model.",
        ),
        EncoderDescriptor(
            encoder_id=CLIP_VIT_B32_ID,
            family="clip",
            version="1",
            status="optional_dependency",
            model_id="openai/clip-vit-base-patch32",
            embedding_source="image embedding",
            license_status=(
                "Must be reviewed and recorded before distribution."
            ),
            notes="Legacy-comparison family only; not promoted by name.",
        ),
        EncoderDescriptor(
            encoder_id=DINOV3_VITS16_ID,
            family="dinov3",
            version="1",
            status="optional_dependency",
            model_id="facebook/dinov3-vits16-pretrain-lvd1689m",
            embedding_source="pooled image embedding",
            license_status=(
                "DINOv3 License; product/distribution use must be "
                "reviewed before promotion."
            ),
            notes="Small DINOv3 candidate for controlled comparison.",
        ),
    )
    for item in items:
        item.validate()
    return items


def get_encoder_descriptor(encoder_id: str) -> EncoderDescriptor:
    for item in encoder_registry():
        if item.encoder_id == encoder_id:
            return item
    raise KeyError(f"Unknown encoder_id: {encoder_id}")
