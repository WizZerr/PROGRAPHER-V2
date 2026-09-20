from pathlib import Path

import exifread

from app.schemas.metadata import PhotoMetadata


class MetadataReadError(RuntimeError):
    pass


TAG_MAP = {
    "make": "Image Make",
    "model": "Image Model",
    "date_time_original": "EXIF DateTimeOriginal",
    "exposure_time": "EXIF ExposureTime",
    "f_number": "EXIF FNumber",
    "iso": "EXIF ISOSpeedRatings",
    "focal_length": "EXIF FocalLength",
}


def _tag_to_text(tags: dict, key: str) -> str | None:
    tag = tags.get(key)

    if tag is None:
        return None

    value = str(tag).strip()
    return value or None


def read_photo_metadata(path_value: str) -> PhotoMetadata:
    path = Path(path_value).expanduser()

    if not path.exists():
        raise MetadataReadError(f"File does not exist: {path}")

    if not path.is_file():
        raise MetadataReadError(f"Path is not a file: {path}")

    try:
        with path.open("rb") as handle:
            tags = exifread.process_file(
                handle,
                details=False,
                strict=False,
            )
    except Exception as exc:
        raise MetadataReadError(
            f"Metadata read failed for {path.name}: {exc}"
        ) from exc

    values = {
        field_name: _tag_to_text(tags, exif_key)
        for field_name, exif_key in TAG_MAP.items()
    }

    has_metadata = any(value is not None for value in values.values())

    return PhotoMetadata(
        path=str(path.resolve()),
        status="ok" if has_metadata else "missing",
        **values,
    )
