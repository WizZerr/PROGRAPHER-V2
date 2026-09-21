from app.brain_v2.components import RawInputRecord
from app.brain_v2.contracts import CameraInfo
from app.brain_v2.features import MetadataFeatureExtractor
from app.brain_v2.preprocessing import MetadataPreprocessor


def test_missing_metadata_gets_separate_missing_flag() -> None:
    raw = RawInputRecord(
        source_fingerprint="source",
        event_id="event",
        camera=CameraInfo(model="Nikon Z6 II"),
        captured_at=None,
        raw_wb=(1.8, 1.0, 1.4, 1.0),
        exif={
            "iso": 400,
            "aperture": 2.8,
        },
        missing_fields=(
            "shutter_seconds",
            "focal_length_mm",
        ),
    )

    preprocessed = MetadataPreprocessor().run(raw)
    result = MetadataFeatureExtractor().run(preprocessed)

    features = dict(
        zip(
            result.features.feature_names,
            result.features.values,
        )
    )

    assert features["iso"] == 400.0
    assert features["iso__missing"] == 0.0
    assert features["shutter_seconds"] == 0.0
    assert features["shutter_seconds__missing"] == 1.0
    assert features["focal_length_mm__missing"] == 1.0
