from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageCms, ImageOps


WORKING_COLOR_SPACE = "srgb-iec61966-2.1-v1"
JPEG_COLOR_CONTRACT_VERSION = "jpeg-color-exif-icc-srgb-v1"
JPEG_INTEGRITY_SCHEMA = "prographer.jpeg-integrity.v1"
DATASET_SNAPSHOT_SCHEMA = "prographer.dataset-snapshot.v1"
MIN_CONFIDENT_INLIER_RATIO = 0.55
PERCEPTUAL_HASH_VERSION = "phash-dct64-v1"
JPEG_CONTAINER_FORMATS = {"JPEG", "MPO"}


class JpegIntegrityError(ValueError):
    pass


class DatasetSnapshotChangedError(ValueError):
    pass


@dataclass(frozen=True)
class JpegDecodeEvidence:
    path: str
    stored_width: int
    stored_height: int
    display_width: int
    display_height: int
    exif_orientation: int
    source_mode: str
    bit_depth: int
    icc_present: bool
    icc_sha256: str | None
    icc_profile_name: str | None
    color_action: str
    camera_make: str | None
    camera_model: str | None
    lens_model: str | None
    iso: int | None
    exposure_time_seconds: float | None
    f_number: float | None
    focal_length_mm: float | None
    mean_luma: float
    shadow_fraction: float
    highlight_fraction: float
    lighting_bucket: str
    perceptual_hash64: str
    perceptual_hash_version: str = PERCEPTUAL_HASH_VERSION
    working_color_space: str = WORKING_COLOR_SPACE


@dataclass(frozen=True)
class EditScopeEvidence:
    scope: str
    affine_residual_p90_255: float
    changed_pixel_fraction: float
    mean_absolute_delta_255: float


@dataclass(frozen=True)
class GeometryEvidence:
    action: str
    usable: bool
    original_width: int
    original_height: int
    edited_width: int
    edited_height: int
    aspect_ratio_relative_error: float
    feature_matches: int
    inliers: int
    inlier_ratio: float
    coverage_ratio: float | None
    rotation_degrees: float | None
    mirrored: bool | None
    edge_similarity: float | None
    note: str


def sha256_file(path: str | Path) -> str:
    source = Path(path)
    digest = sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _profile_name(profile: ImageCms.ImageCmsProfile) -> str | None:
    try:
        name = ImageCms.getProfileName(profile).strip()
    except Exception:
        return None
    return name or None


def perceptual_hash64(rgb: np.ndarray) -> str:
    """Return a 64-bit DCT perceptual hash from normalized working-space RGB."""
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("perceptual_hash64 expects HxWx3 RGB")
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(small.astype(np.float32))
    block = dct[:8, :8].reshape(-1)
    median = float(np.median(block[1:]))
    bits = block > median
    value = 0
    for bit in bits:
        value = (value << 1) | int(bool(bit))
    return f"{value:016x}"


def perceptual_hamming_distance(left: str, right: str) -> int:
    if len(left) != 16 or len(right) != 16:
        raise ValueError("expected 64-bit perceptual hashes encoded as 16 hex chars")
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _exif_text(exif, tag: int) -> str | None:
    value = exif.get(tag)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _exif_float(exif, tag: int) -> float | None:
    value = exif.get(tag)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        try:
            return float(value.numerator) / float(value.denominator)
        except Exception:
            return None


def _lighting_stats(rgb: np.ndarray) -> tuple[float, float, float, str]:
    normalized = rgb.astype(np.float32) / 255.0
    luma = (
        normalized[:, :, 0] * 0.2126
        + normalized[:, :, 1] * 0.7152
        + normalized[:, :, 2] * 0.0722
    )
    mean_luma = float(luma.mean())
    shadow_fraction = float((luma < 0.18).mean())
    highlight_fraction = float((luma > 0.82).mean())

    if mean_luma < 0.28:
        bucket = "low_key"
    elif mean_luma > 0.72:
        bucket = "high_key"
    elif shadow_fraction >= 0.18 and highlight_fraction >= 0.08:
        bucket = "mixed_contrast"
    else:
        bucket = "mid_tone"

    return mean_luma, shadow_fraction, highlight_fraction, bucket


def analyze_edit_scope(
    original_rgb: np.ndarray,
    edited_rgb: np.ndarray,
) -> EditScopeEvidence:
    """
    Coarse coverage label, not a retouch detector.

    Fit a global affine RGB transform. Low residual -> global-like.
    High residual -> local-or-complex suspected. The latter intentionally
    combines local retouching with nonlinear/global edits that this simple
    coverage model cannot explain.
    """
    oh, ow = original_rgb.shape[:2]
    eh, ew = edited_rgb.shape[:2]
    if (oh, ow) != (eh, ew):
        edited_rgb = cv2.resize(
            edited_rgb,
            (ow, oh),
            interpolation=cv2.INTER_AREA,
        )

    max_edge = max(oh, ow)
    if max_edge > 640:
        scale = 640.0 / float(max_edge)
        target = (max(1, round(ow * scale)), max(1, round(oh * scale)))
        original_rgb = cv2.resize(original_rgb, target, interpolation=cv2.INTER_AREA)
        edited_rgb = cv2.resize(edited_rgb, target, interpolation=cv2.INTER_AREA)

    original = original_rgb.astype(np.float32)
    edited = edited_rgb.astype(np.float32)
    delta = np.abs(edited - original)
    pixel_delta = delta.max(axis=2)
    changed_fraction = float((pixel_delta > 3.0).mean())
    mean_delta = float(delta.mean())

    if changed_fraction <= 0.01 and mean_delta <= 1.0:
        return EditScopeEvidence(
            scope="identity_like",
            affine_residual_p90_255=0.0,
            changed_pixel_fraction=changed_fraction,
            mean_absolute_delta_255=mean_delta,
        )

    x = original.reshape(-1, 3)
    y = edited.reshape(-1, 3)
    sample_count = x.shape[0]
    if sample_count > 50000:
        indices = np.linspace(0, sample_count - 1, 50000, dtype=np.int64)
        x_fit = x[indices]
        y_fit = y[indices]
    else:
        x_fit = x
        y_fit = y

    design = np.concatenate(
        [x_fit, np.ones((x_fit.shape[0], 1), dtype=np.float32)],
        axis=1,
    )
    coefficients, *_ = np.linalg.lstsq(design, y_fit, rcond=None)

    full_design = np.concatenate(
        [x, np.ones((x.shape[0], 1), dtype=np.float32)],
        axis=1,
    )
    predicted = np.clip(full_design @ coefficients, 0.0, 255.0)
    residual = np.abs(predicted - y)
    per_pixel_residual = residual.max(axis=1)
    p90 = float(np.percentile(per_pixel_residual, 90))

    scope = (
        "global_like"
        if p90 <= 8.0
        else "local_or_complex_suspected"
    )
    return EditScopeEvidence(
        scope=scope,
        affine_residual_p90_255=p90,
        changed_pixel_fraction=changed_fraction,
        mean_absolute_delta_255=mean_delta,
    )


def read_jpeg_working_rgb(
    path: str | Path,
) -> tuple[np.ndarray, JpegDecodeEvidence]:
    """
    Decode one JPEG into the single Release-1 research working space.

    - Embedded ICC -> converted to sRGB.
    - RGB/L without ICC -> explicit sRGB assumption.
    - non-RGB without ICC -> rejected rather than silently guessed.
    - EXIF orientation -> normalized into displayed pixel orientation.
    """
    source = Path(path).expanduser().resolve(strict=True)

    try:
        with Image.open(source) as opened:
            container_format = str(opened.format or "").upper()
            if container_format not in JPEG_CONTAINER_FORMATS:
                detected = container_format or "unknown"
                raise JpegIntegrityError(
                    "unsupported_media: expected JPEG-compatible JPEG/MPO, "
                    f"detected {detected}: {source}"
                )

            # Pillow promotes JPEG files with a valid MPF index to MPO.
            # Release 1 edits the primary photograph only; auxiliary MPO
            # frames are not part of the JPEG EditRecipe contract.
            if container_format == "MPO":
                try:
                    opened.seek(0)
                except EOFError as exc:
                    raise JpegIntegrityError(
                        f"mpo_primary_frame_unavailable: {source.name}"
                    ) from exc

            stored_width, stored_height = opened.size
            source_mode = opened.mode

            exif = opened.getexif()
            raw_orientation = exif.get(274, 1)
            try:
                orientation = int(raw_orientation or 1)
            except (TypeError, ValueError):
                orientation = 1
            if orientation not in range(1, 9):
                orientation = 1

            camera_make = _exif_text(exif, 271)
            camera_model = _exif_text(exif, 272)
            lens_model = _exif_text(exif, 42036)
            iso_value = _exif_float(exif, 34855)
            iso = int(round(iso_value)) if iso_value is not None else None
            exposure_time = _exif_float(exif, 33434)
            f_number = _exif_float(exif, 33437)
            focal_length = _exif_float(exif, 37386)

            icc_payload = opened.info.get("icc_profile")
            icc_sha = (
                sha256(icc_payload).hexdigest()
                if isinstance(icc_payload, (bytes, bytearray)) and icc_payload
                else None
            )
            profile_name: str | None = None

            # Normalize display orientation before color conversion. Some
            # color transforms do not preserve EXIF metadata, so reversing this
            # order can silently lose orientation 2..8.
            working = ImageOps.exif_transpose(opened.copy())

            if icc_sha is not None:
                try:
                    source_profile = ImageCms.ImageCmsProfile(
                        BytesIO(icc_payload)
                    )
                    destination_profile = ImageCms.createProfile("sRGB")
                    profile_name = _profile_name(source_profile)
                    working = ImageCms.profileToProfile(
                        working,
                        source_profile,
                        destination_profile,
                        outputMode="RGB",
                    )
                    color_action = "icc_to_srgb"
                except Exception as exc:
                    raise JpegIntegrityError(
                        f"icc_conversion_failed: {source.name}"
                    ) from exc
            else:
                if source_mode not in {"RGB", "L"}:
                    raise JpegIntegrityError(
                        "missing_icc_for_non_rgb: "
                        f"{source.name} mode={source_mode}"
                    )
                working = working.convert("RGB")
                color_action = "assume_srgb_no_icc"

            working = working.convert("RGB")
            rgb = np.asarray(working, dtype=np.uint8).copy()
            display_height, display_width = rgb.shape[:2]
            phash = perceptual_hash64(rgb)
            (
                mean_luma,
                shadow_fraction,
                highlight_fraction,
                lighting_bucket,
            ) = _lighting_stats(rgb)

            return rgb, JpegDecodeEvidence(
                path=str(source),
                stored_width=int(stored_width),
                stored_height=int(stored_height),
                display_width=int(display_width),
                display_height=int(display_height),
                exif_orientation=orientation,
                source_mode=source_mode,
                bit_depth=8,
                icc_present=icc_sha is not None,
                icc_sha256=icc_sha,
                icc_profile_name=profile_name,
                color_action=color_action,
                camera_make=camera_make,
                camera_model=camera_model,
                lens_model=lens_model,
                iso=iso,
                exposure_time_seconds=exposure_time,
                f_number=f_number,
                focal_length_mm=focal_length,
                mean_luma=mean_luma,
                shadow_fraction=shadow_fraction,
                highlight_fraction=highlight_fraction,
                lighting_bucket=lighting_bucket,
                perceptual_hash64=phash,
            )
    except JpegIntegrityError:
        raise
    except (OSError, ValueError) as exc:
        raise JpegIntegrityError(
            f"jpeg_decode_failed: {source.name}"
        ) from exc


def _resize_for_geometry(
    image: np.ndarray,
    max_edge: int = 1200,
) -> np.ndarray:
    height, width = image.shape[:2]
    largest = max(height, width)
    if largest <= max_edge:
        return image

    scale = max_edge / float(largest)
    target = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )
    return cv2.resize(image, target, interpolation=cv2.INTER_AREA)


def _normalized_gray(image: np.ndarray) -> np.ndarray:
    resized = _resize_for_geometry(image)
    gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
    return cv2.equalizeHist(gray)


def _normalize_angle(degrees: float) -> float:
    value = (degrees + 180.0) % 360.0 - 180.0
    if math.isclose(value, -180.0, abs_tol=1e-9):
        return 180.0
    return value


def _estimate_homography(
    original_gray: np.ndarray,
    edited_gray: np.ndarray,
) -> tuple[np.ndarray | None, int, int, float]:
    detector = cv2.ORB_create(
        nfeatures=2400,
        fastThreshold=7,
    )
    original_keypoints, original_descriptors = detector.detectAndCompute(
        original_gray,
        None,
    )
    edited_keypoints, edited_descriptors = detector.detectAndCompute(
        edited_gray,
        None,
    )

    if (
        original_descriptors is None
        or edited_descriptors is None
        or len(original_keypoints) < 12
        or len(edited_keypoints) < 12
    ):
        return None, 0, 0, 0.0

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    raw_matches = matcher.knnMatch(
        edited_descriptors,
        original_descriptors,
        k=2,
    )
    good = [
        first
        for pair in raw_matches
        if len(pair) == 2
        for first, second in [pair]
        if first.distance < 0.75 * second.distance
    ]
    if len(good) < 12:
        return None, len(good), 0, 0.0

    edited_points = np.float32(
        [edited_keypoints[item.queryIdx].pt for item in good]
    ).reshape(-1, 1, 2)
    original_points = np.float32(
        [original_keypoints[item.trainIdx].pt for item in good]
    ).reshape(-1, 1, 2)

    homography, mask = cv2.findHomography(
        edited_points,
        original_points,
        cv2.RANSAC,
        4.0,
    )
    if homography is None or mask is None:
        return None, len(good), 0, 0.0

    inliers = int(mask.ravel().sum())
    inlier_ratio = inliers / float(len(good))
    if inliers < 8 or inlier_ratio < 0.35:
        return None, len(good), inliers, inlier_ratio

    return homography, len(good), inliers, inlier_ratio


def _blocked_geometry(
    *,
    action: str,
    original_width: int,
    original_height: int,
    edited_width: int,
    edited_height: int,
    aspect_error: float,
    feature_matches: int,
    inliers: int,
    inlier_ratio: float,
    note: str,
    mirrored: bool | None = None,
) -> GeometryEvidence:
    return GeometryEvidence(
        action=action,
        usable=False,
        original_width=original_width,
        original_height=original_height,
        edited_width=edited_width,
        edited_height=edited_height,
        aspect_ratio_relative_error=aspect_error,
        feature_matches=feature_matches,
        inliers=inliers,
        inlier_ratio=inlier_ratio,
        coverage_ratio=None,
        rotation_degrees=None,
        mirrored=mirrored,
        edge_similarity=None,
        note=note,
    )


def _edge_alignment_similarity(
    original_gray: np.ndarray,
    edited_gray: np.ndarray,
    homography: np.ndarray,
) -> float:
    """
    Measure whether the homography aligns actual scene edges, not merely a
    handful of descriptor matches. This separates real crop/resize edits from
    a visually unrelated photo that happened to produce a spurious homography.
    """
    height, width = original_gray.shape[:2]
    warped = cv2.warpPerspective(
        edited_gray,
        homography,
        (width, height),
    )
    valid = cv2.warpPerspective(
        np.full(edited_gray.shape, 255, dtype=np.uint8),
        homography,
        (width, height),
        flags=cv2.INTER_NEAREST,
    ) > 0

    original_edges = cv2.Canny(
        original_gray,
        60,
        140,
    ) > 0
    edited_edges = cv2.Canny(
        warped,
        60,
        140,
    ) > 0

    kernel = np.ones((3, 3), dtype=np.uint8)
    original_dilated = cv2.dilate(
        original_edges.astype(np.uint8),
        kernel,
    ) > 0
    edited_dilated = cv2.dilate(
        edited_edges.astype(np.uint8),
        kernel,
    ) > 0

    edited_valid = edited_edges & valid
    original_valid = original_edges & valid

    precision = float(
        (edited_valid & original_dilated).sum()
    ) / max(1.0, float(edited_valid.sum()))
    recall = float(
        (original_valid & edited_dilated).sum()
    ) / max(1.0, float(original_valid.sum()))

    if precision + recall <= 1e-12:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def analyze_pair_geometry(
    original_rgb: np.ndarray,
    edited_rgb: np.ndarray,
    *,
    aspect_tolerance: float = 0.01,
) -> GeometryEvidence:
    """
    Verify that Original/Edited are the same scene geometry.

    The check is deliberately conservative: uncertain pairs are excluded
    instead of being stretched/resized into an apparently valid target.
    """
    oh, ow = original_rgb.shape[:2]
    eh, ew = edited_rgb.shape[:2]

    original_ratio = ow / float(oh)
    edited_ratio = ew / float(eh)
    aspect_error = abs(original_ratio - edited_ratio) / max(
        abs(edited_ratio),
        1e-9,
    )

    original_gray = _normalized_gray(original_rgb)
    edited_gray = _normalized_gray(edited_rgb)

    homography, matches, inliers, inlier_ratio = _estimate_homography(
        original_gray,
        edited_gray,
    )

    if homography is None:
        # ORB descriptors are not reflection invariant. A second explicit
        # attempt lets us identify a common horizontal/vertical mirror case
        # instead of collapsing it into generic "wrong copy".
        for flip_code in (1, 0):
            flipped = cv2.flip(edited_gray, flip_code)
            mirrored_h, mirrored_matches, mirrored_inliers, mirrored_ratio = (
                _estimate_homography(original_gray, flipped)
            )
            if mirrored_h is not None:
                return _blocked_geometry(
                    action="mirror_mismatch",
                    original_width=ow,
                    original_height=oh,
                    edited_width=ew,
                    edited_height=eh,
                    aspect_error=aspect_error,
                    feature_matches=mirrored_matches,
                    inliers=mirrored_inliers,
                    inlier_ratio=mirrored_ratio,
                    mirrored=True,
                    note=(
                        "mirror/flip geometry detected; exclude until "
                        "mirror-aware recipe support exists"
                    ),
                )

        return _blocked_geometry(
            action="wrong_copy_or_unverified",
            original_width=ow,
            original_height=oh,
            edited_width=ew,
            edited_height=eh,
            aspect_error=aspect_error,
            feature_matches=matches,
            inliers=inliers,
            inlier_ratio=inlier_ratio,
            note=(
                "same-photo geometry could not be verified; "
                "pair is blocked rather than guessed"
            ),
        )

    # A mathematically valid homography is not enough. Unrelated photos can
    # occasionally produce a small accidental correspondence set, especially
    # when they share generic gradients/edges. Be conservative: a weak RANSAC
    # consensus is treated as an unverified/wrong-copy pair rather than as crop.
    if inlier_ratio < MIN_CONFIDENT_INLIER_RATIO:
        return _blocked_geometry(
            action="wrong_copy_or_unverified",
            original_width=ow,
            original_height=oh,
            edited_width=ew,
            edited_height=eh,
            aspect_error=aspect_error,
            feature_matches=matches,
            inliers=inliers,
            inlier_ratio=inlier_ratio,
            note=(
                "homography consensus is too weak to prove same-photo geometry; "
                "pair is blocked rather than guessed"
            ),
        )

    oh2, ow2 = original_gray.shape[:2]
    eh2, ew2 = edited_gray.shape[:2]
    corners = np.float32(
        [
            [0, 0],
            [ew2 - 1, 0],
            [ew2 - 1, eh2 - 1],
            [0, eh2 - 1],
        ]
    ).reshape(-1, 1, 2)
    mapped = cv2.perspectiveTransform(
        corners,
        homography,
    ).reshape(-1, 2)

    mapped_area = abs(
        float(cv2.contourArea(mapped.astype(np.float32)))
    )
    original_area = max(
        1.0,
        float((ow2 - 1) * (oh2 - 1)),
    )
    coverage_ratio = mapped_area / original_area

    top = mapped[1] - mapped[0]
    left = mapped[3] - mapped[0]
    cross = float(
        top[0] * left[1] - top[1] * left[0]
    )
    mirrored = cross < 0.0
    rotation = _normalize_angle(
        math.degrees(
            math.atan2(
                float(top[1]),
                float(top[0]),
            )
        )
    )

    edge_similarity = _edge_alignment_similarity(
        original_gray,
        edited_gray,
        homography,
    )
    if edge_similarity < 0.40:
        return GeometryEvidence(
            action="wrong_copy_or_unverified",
            usable=False,
            original_width=ow,
            original_height=oh,
            edited_width=ew,
            edited_height=eh,
            aspect_ratio_relative_error=aspect_error,
            feature_matches=matches,
            inliers=inliers,
            inlier_ratio=inlier_ratio,
            coverage_ratio=coverage_ratio,
            rotation_degrees=rotation,
            mirrored=mirrored,
            edge_similarity=edge_similarity,
            note=(
                "homography exists but aligned scene edges do not match strongly "
                "enough; block as wrong-copy/unverified"
            ),
        )

    if mirrored:
        action = "mirror_mismatch"
        usable = False
        note = "mirror/flip geometry detected"
    elif abs(rotation) > 12.0:
        action = "rotation_mismatch"
        usable = False
        note = (
            "residual rotation detected after EXIF normalization "
            f"({rotation:.1f}°)"
        )
    elif coverage_ratio < 0.90 or coverage_ratio > 1.10:
        action = (
            "crop_same_ratio"
            if aspect_error <= aspect_tolerance
            else "crop_or_geometry_mismatch"
        )
        usable = False
        note = (
            "content alignment indicates a crop/geometry change; "
            "exclude until crop-aware recipe support exists"
        )
    elif aspect_error > aspect_tolerance:
        action = "crop_or_geometry_mismatch"
        usable = False
        note = "display aspect ratio differs beyond tolerance"
    elif (ow, oh) == (ew, eh):
        action = "same_dimensions"
        usable = True
        note = ""
    else:
        action = "resize_only"
        usable = True
        note = (
            "same aligned content with compatible aspect ratio; "
            "resize is allowed"
        )

    return GeometryEvidence(
        action=action,
        usable=usable,
        original_width=ow,
        original_height=oh,
        edited_width=ew,
        edited_height=eh,
        aspect_ratio_relative_error=aspect_error,
        feature_matches=matches,
        inliers=inliers,
        inlier_ratio=inlier_ratio,
        coverage_ratio=coverage_ratio,
        rotation_degrees=rotation,
        mirrored=mirrored,
        edge_similarity=edge_similarity,
        note=note,
    )


def inspect_jpeg_pair(
    original: str | Path,
    edited: str | Path,
    *,
    aspect_tolerance: float = 0.01,
) -> tuple[
    JpegDecodeEvidence,
    JpegDecodeEvidence,
    GeometryEvidence,
]:
    original_rgb, original_evidence = read_jpeg_working_rgb(
        original
    )
    edited_rgb, edited_evidence = read_jpeg_working_rgb(
        edited
    )
    geometry = analyze_pair_geometry(
        original_rgb,
        edited_rgb,
        aspect_tolerance=aspect_tolerance,
    )
    return original_evidence, edited_evidence, geometry


def freeze_dataset_snapshot(
    entries: Iterable[dict],
) -> dict:
    """
    Freeze hashes already calculated during intake without re-reading every
    large source file a second time.
    """
    files: list[dict] = []
    for raw in entries:
        item = {
            "role": str(raw["role"]),
            "pair_id": str(raw["pair_id"]),
            "path": str(
                Path(raw["path"])
                .expanduser()
                .resolve(strict=True)
            ),
            "size_bytes": int(raw["size_bytes"]),
            "modified_ns": int(raw["modified_ns"]),
            "sha256": str(raw["sha256"]),
        }
        if not item["sha256"]:
            raise ValueError("snapshot entry is missing sha256")
        files.append(item)

    files.sort(
        key=lambda item: (
            item["pair_id"],
            item["role"],
            item["path"].casefold(),
        )
    )

    # Paths deliberately do not participate in snapshot identity. A verified
    # relocation may update locators without changing the dataset bytes.
    identity = [
        {
            "role": item["role"],
            "pair_id": item["pair_id"],
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in files
    ]
    snapshot_id = sha256(
        json.dumps(
            identity,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return {
        "schema": DATASET_SNAPSHOT_SCHEMA,
        "snapshot_id": snapshot_id,
        "files": files,
    }


def validate_dataset_snapshot(
    snapshot: dict,
    *,
    expected_snapshot_id: str | None = None,
) -> None:
    if snapshot.get("schema") != DATASET_SNAPSHOT_SCHEMA:
        raise DatasetSnapshotChangedError(
            "unsupported_dataset_snapshot_schema"
        )

    if (
        expected_snapshot_id is not None
        and snapshot.get("snapshot_id") != expected_snapshot_id
    ):
        raise DatasetSnapshotChangedError(
            "dataset_snapshot_id_mismatch"
        )

    for item in snapshot.get("files") or []:
        path = Path(item["path"])
        if not path.is_file():
            raise DatasetSnapshotChangedError(
                "source_missing: "
                f"{item['role']}:{item['pair_id']}:{path}"
            )

        stat = path.stat()
        if int(stat.st_size) != int(item["size_bytes"]):
            raise DatasetSnapshotChangedError(
                "source_changed_size: "
                f"{item['role']}:{item['pair_id']}:{path}"
            )

        current_sha = sha256_file(path)
        if current_sha != item["sha256"]:
            raise DatasetSnapshotChangedError(
                "source_changed_hash: "
                f"{item['role']}:{item['pair_id']}:{path}"
            )


def load_and_validate_dataset_snapshot(
    path: str | Path,
    *,
    expected_snapshot_id: str | None = None,
) -> dict:
    snapshot_path = Path(path).expanduser().resolve(strict=True)
    snapshot = json.loads(
        snapshot_path.read_text(encoding="utf-8")
    )
    validate_dataset_snapshot(
        snapshot,
        expected_snapshot_id=expected_snapshot_id,
    )
    return snapshot
