from pathlib import Path

import pytest

from app.services.metadata_service import MetadataReadError, read_photo_metadata


def test_missing_file_raises_explicit_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.CR3"

    with pytest.raises(MetadataReadError):
        read_photo_metadata(str(missing))


def test_file_without_metadata_returns_none_not_zero(tmp_path: Path) -> None:
    sample = tmp_path / "empty.bin"
    sample.write_bytes(b"not-an-image")

    result = read_photo_metadata(str(sample))

    assert result.status == "missing"
    assert result.make is None
    assert result.model is None
    assert result.iso is None
    assert result.f_number is None
    assert result.exposure_time is None
    assert result.focal_length is None
