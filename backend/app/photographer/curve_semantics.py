"""RAW-CAT-01E.01: conservative parser for Lightroom point-curve tables.

This module does *not* run Lua or render images. Only an explicitly supported
flat numeric sequence is decoded; all other structures stay undecoded.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re

# Numeric tokens are deliberately strict: expressions, names, nested values,
# Lua function calls and NaN/Infinity are not accepted.
_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")


@dataclass(frozen=True)
class PointCurve:
    points: tuple[tuple[int, int], ...]

    @property
    def is_linear(self) -> bool:
        return all(x == y for x, y in self.points)


def decode_flat_point_curve(serialized: str) -> PointCurve:
    """Decode a flat Lua-style `{x, y, x, y, ...}` point curve.

    This is *syntactic* decoding only, not Lightroom/Adobe parity validation.
    Full-scale 0..255 integral points are the only supported representation.
    """
    s = serialized.strip()
    if not (s.startswith("{") and s.endswith("}")):
        raise ValueError("not_a_braced_table")
    body = s[1:-1].strip()
    parts = [part.strip() for part in body.split(",")]
    if parts and parts[-1] == "":  # Lua trailing comma
        parts.pop()
    if len(parts) < 4 or len(parts) % 2:
        raise ValueError("invalid_number_of_coordinates")
    if len(parts) > 512:
        raise ValueError("too_many_coordinates")
    values = []
    for part in parts:
        if not _NUMBER.fullmatch(part):
            raise ValueError("unsupported_non_numeric_or_nested_curve")
        numeric = float(part)
        if not math.isfinite(numeric) or not (0 <= numeric <= 255) or not numeric.is_integer():
            raise ValueError("invalid_coordinate")
        values.append(int(numeric))
    points = tuple(zip(values[::2], values[1::2]))
    if any(points[i][0] >= points[i + 1][0] for i in range(len(points) - 1)):
        raise ValueError("x_coordinates_not_strictly_increasing")
    return PointCurve(points)


def describe_curve(serialized: str) -> dict[str, object]:
    """Return safe explicit metadata and points for supported forms.

    Keeping a fingerprint on failed decode lets research compare structures
    without fabricating points or hiding any unsupported curve.
    """
    result: dict[str, object] = {
        "present": True,
        "decoded": False,
        "serialized_length": len(serialized),
        "sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
    }
    try:
        curve = decode_flat_point_curve(serialized)
    except (ValueError, OverflowError) as exc:
        result["undecoded_reason"] = str(exc)
        return result
    result.update(
        decoded=True,
        structure="flat_numeric_point_curve",
        points=[list(pair) for pair in curve.points],
        is_linear=curve.is_linear,
        **{"lightroom_semantics_validated": False},
    )
    return result
