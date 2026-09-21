from app.brain_v2.components import RawInputRecord
from app.brain_v2.contracts import CameraInfo
from app.brain_v2.factory import create_experimental_pipeline


def make_raw() -> RawInputRecord:
    return RawInputRecord(
        source_fingerprint="source-1",
        event_id="event-1",
        camera=CameraInfo(
            make="Canon",
            model="EOS R6",
        ),
        captured_at="2026-09-20T18:00:00",
        raw_wb=(2.0, 1.0, 1.5, 1.0),
        exif={
            "iso": 800,
            "shutter_seconds": 0.01,
            "aperture": 2.8,
            "focal_length_mm": 35.0,
        },
        missing_fields=(),
    )


def test_pipeline_executes_components_in_explicit_order() -> None:
    result = create_experimental_pipeline().run(make_raw())

    assert result.executed_components == (
        "preprocessing",
        "features",
        "base_model",
        "photographer_adapter",
        "event_context",
        "quality_control",
    )


def test_noop_components_do_not_fake_personalization_or_context() -> None:
    result = create_experimental_pipeline().run(make_raw())

    assert result.adapted_recipe == result.base_recipe
    assert result.final_recipe == result.base_recipe
    assert result.final_recipe.scene_context_applied is False


def test_first_path_requires_full_review_without_fake_confidence() -> None:
    result = create_experimental_pipeline().run(make_raw())

    assert result.quality.availability.state == "not_available"
    assert result.quality.requires_full_review is True
    assert result.quality.confidence is None
    assert result.final_recipe.critic_checked is False
