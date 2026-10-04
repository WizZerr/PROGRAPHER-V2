from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageCms

from app.datasets.jpeg_integrity import JpegIntegrityError, read_jpeg_working_rgb
from app.rendering.jpeg_product_render import (
    assert_current_jpeg_revision,
    resolve_jpeg_product_source,
)
from app.rendering.jpeg_renderer import render_recipe_uint8


JPEG_EXPORT_CONTRACT_VERSION = "jpeg-export-encoded-v1"
JPEG_EXPORT_DEFAULT_QUALITY = 95
JPEG_EXPORT_MIN_QUALITY = 1
JPEG_EXPORT_MAX_QUALITY = 100
JPEG_EXPORT_ICC_POLICIES = {"embed_srgb", "omit"}
JPEG_EXPORT_METADATA_POLICIES = {"preserve", "strip"}

_EXIF_ORIENTATION = 274
_EXIF_GPS_INFO = 34853
_EXIF_IMAGE_WIDTH = 256
_EXIF_IMAGE_HEIGHT = 257
_EXIF_PIXEL_X_DIMENSION = 40962
_EXIF_PIXEL_Y_DIMENSION = 40963


class JpegExportError(ValueError):
    pass


@dataclass(frozen=True)
class JpegExportOptions:
    quality: int = JPEG_EXPORT_DEFAULT_QUALITY
    max_edge: int | None = None
    icc_policy: str = "embed_srgb"
    metadata_policy: str = "preserve"
    include_gps: bool = False


@dataclass(frozen=True)
class JpegEncodedArtifact:
    payload: bytes
    media_type: str
    contract_version: str
    revision: int
    recipe_sha256: str
    width: int
    height: int
    quality: int
    icc_policy: str
    metadata_policy: str
    gps_included: bool


def validate_jpeg_export_options(options: JpegExportOptions) -> JpegExportOptions:
    if isinstance(options.quality, bool) or not isinstance(options.quality, int):
        raise JpegExportError("JPEG quality must be an integer")
    if not JPEG_EXPORT_MIN_QUALITY <= options.quality <= JPEG_EXPORT_MAX_QUALITY:
        raise JpegExportError("JPEG quality must be between 1 and 100")

    if options.max_edge is not None:
        if isinstance(options.max_edge, bool) or not isinstance(options.max_edge, int):
            raise JpegExportError("max_edge must be an integer or null")
        if options.max_edge < 1:
            raise JpegExportError("max_edge must be greater than zero")

    if options.icc_policy not in JPEG_EXPORT_ICC_POLICIES:
        raise JpegExportError("unsupported JPEG ICC policy")
    if options.metadata_policy not in JPEG_EXPORT_METADATA_POLICIES:
        raise JpegExportError("unsupported JPEG metadata policy")
    if options.metadata_policy == "strip" and options.include_gps:
        raise JpegExportError("GPS cannot be included when metadata is stripped")
    if not isinstance(options.include_gps, bool):
        raise JpegExportError("include_gps must be boolean")

    return options


def _resize_for_export(rgb: np.ndarray, max_edge: int | None) -> np.ndarray:
    if max_edge is None:
        return rgb

    height, width = rgb.shape[:2]
    largest = max(height, width)
    if largest <= max_edge:
        return rgb

    scale = max_edge / float(largest)
    target = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )
    return cv2.resize(rgb, target, interpolation=cv2.INTER_AREA)


def _srgb_icc_bytes() -> bytes:
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    return profile.tobytes()


def _export_exif_bytes(
    source_path,
    *,
    metadata_policy: str,
    include_gps: bool,
    width: int,
    height: int,
) -> tuple[bytes | None, bool]:
    if metadata_policy == "strip":
        return None, False

    try:
        with Image.open(source_path) as opened:
            source_exif = opened.getexif()
            if not source_exif:
                return None, False
            source_has_gps = _EXIF_GPS_INFO in source_exif
            payload = source_exif.tobytes()
    except (OSError, ValueError) as exc:
        raise JpegExportError("failed to read source EXIF metadata") from exc

    export_exif = Image.Exif()
    try:
        export_exif.load(payload)
    except (OSError, ValueError, TypeError) as exc:
        raise JpegExportError("failed to normalize source EXIF metadata") from exc

    export_exif[_EXIF_ORIENTATION] = 1
    export_exif[_EXIF_IMAGE_WIDTH] = int(width)
    export_exif[_EXIF_IMAGE_HEIGHT] = int(height)
    export_exif[_EXIF_PIXEL_X_DIMENSION] = int(width)
    export_exif[_EXIF_PIXEL_Y_DIMENSION] = int(height)

    if not include_gps and _EXIF_GPS_INFO in export_exif:
        del export_exif[_EXIF_GPS_INFO]

    gps_included = bool(include_gps and source_has_gps)
    return export_exif.tobytes(), gps_included


def _encode_jpeg(
    rgb: np.ndarray,
    *,
    source_path,
    options: JpegExportOptions,
) -> tuple[bytes, bool]:
    height, width = rgb.shape[:2]
    exif_payload, gps_included = _export_exif_bytes(
        source_path,
        metadata_policy=options.metadata_policy,
        include_gps=options.include_gps,
        width=int(width),
        height=int(height),
    )
    icc_payload = (
        _srgb_icc_bytes()
        if options.icc_policy == "embed_srgb"
        else None
    )

    output = BytesIO()
    save_kwargs: dict[str, Any] = {
        "format": "JPEG",
        "quality": options.quality,
        "subsampling": 0,
        "optimize": False,
        "progressive": False,
    }
    if icc_payload is not None:
        save_kwargs["icc_profile"] = icc_payload
    if exif_payload is not None:
        save_kwargs["exif"] = exif_payload

    Image.fromarray(rgb).save(output, **save_kwargs)
    return output.getvalue(), gps_included


def _verify_encoded_jpeg(
    payload: bytes,
    *,
    expected_width: int,
    expected_height: int,
    options: JpegExportOptions,
    expected_gps_included: bool,
) -> None:
    try:
        with Image.open(BytesIO(payload)) as encoded:
            encoded.load()
            if encoded.format != "JPEG":
                raise JpegExportError("encoded export is not JPEG")
            if encoded.mode != "RGB":
                raise JpegExportError("encoded export is not RGB")
            if encoded.size != (expected_width, expected_height):
                raise JpegExportError(
                    "encoded JPEG dimensions do not match render"
                )

            icc_present = bool(encoded.info.get("icc_profile"))
            expected_icc = options.icc_policy == "embed_srgb"
            if icc_present != expected_icc:
                raise JpegExportError(
                    "encoded JPEG ICC policy was not preserved"
                )

            exif = encoded.getexif()
            if options.metadata_policy == "strip":
                if len(exif) != 0:
                    raise JpegExportError(
                        "metadata strip policy left EXIF data"
                    )
            else:
                orientation = int(exif.get(_EXIF_ORIENTATION, 1) or 1)
                if orientation != 1:
                    raise JpegExportError(
                        "encoded JPEG orientation is not normalized"
                    )
                gps_present = _EXIF_GPS_INFO in exif
                if gps_present != expected_gps_included:
                    raise JpegExportError(
                        "encoded JPEG GPS policy was not preserved"
                    )
    except JpegExportError:
        raise
    except (OSError, ValueError) as exc:
        raise JpegExportError(
            "encoded JPEG failed reopen verification"
        ) from exc


def encode_jpeg_export(
    *,
    event_id: str,
    fingerprint: str,
    recipe: dict[str, Any],
    revision: int,
    options: JpegExportOptions,
) -> JpegEncodedArtifact:
    options = validate_jpeg_export_options(options)

    recipe_sha256 = assert_current_jpeg_revision(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=recipe,
        revision=revision,
    )
    source_path = resolve_jpeg_product_source(event_id, fingerprint)

    try:
        source_rgb, _ = read_jpeg_working_rgb(source_path)
    except (JpegIntegrityError, OSError) as exc:
        raise JpegExportError(str(exc)) from exc

    rendered = render_recipe_uint8(source_rgb, recipe)
    sized = _resize_for_export(rendered, options.max_edge)
    height, width = sized.shape[:2]

    payload, gps_included = _encode_jpeg(
        sized,
        source_path=source_path,
        options=options,
    )
    _verify_encoded_jpeg(
        payload,
        expected_width=int(width),
        expected_height=int(height),
        options=options,
        expected_gps_included=gps_included,
    )

    return JpegEncodedArtifact(
        payload=payload,
        media_type="image/jpeg",
        contract_version=JPEG_EXPORT_CONTRACT_VERSION,
        revision=revision,
        recipe_sha256=recipe_sha256,
        width=int(width),
        height=int(height),
        quality=options.quality,
        icc_policy=options.icc_policy,
        metadata_policy=options.metadata_policy,
        gps_included=gps_included,
    )
