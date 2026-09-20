from pathlib import Path

from app.datasets.contracts import SourceMetadata
from app.datasets.metadata import extract_source_metadata


def test_invalid_raw_keeps_missing_metadata_missing(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "fake.CR3"
    raw.write_bytes(b"not-a-real-raw")

    metadata = extract_source_metadata(raw)

    assert metadata == SourceMetadata()
    assert metadata.camera_model is None
    assert metadata.raw_wb is None
