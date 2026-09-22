from app.brain_v2.vision_encoders.registry import (
    CLIP_VIT_B32_ID,
    DINOV3_VITS16_ID,
    SIMPLE_MEASURED_ID,
    encoder_registry,
)


def test_encoder_registry_has_three_controlled_candidates() -> None:
    ids = {item.encoder_id for item in encoder_registry()}
    assert ids == {
        SIMPLE_MEASURED_ID,
        CLIP_VIT_B32_ID,
        DINOV3_VITS16_ID,
    }


def test_pretrained_candidates_are_not_marked_available_by_default() -> None:
    by_id = {
        item.encoder_id: item
        for item in encoder_registry()
    }
    assert by_id[CLIP_VIT_B32_ID].status == "optional_dependency"
    assert by_id[DINOV3_VITS16_ID].status == "optional_dependency"
    assert by_id[SIMPLE_MEASURED_ID].status == "available"
