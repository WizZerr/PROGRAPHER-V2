"""As-shot white balance of a Smart Preview in Lightroom's units (Kelvin + Tint), from the DNG's own tags.

Lightroom stores a Custom white balance as Temperature/Tint, but an "As Shot" one is the camera's AsShotNeutral.
To compare the two (the research rule: temperature moves in mired relative to As Shot), the neutral is converted
the way the DNG SDK does it:
  neutral -> xy  : iterate XYZ = inverse(AnalogBalance x CameraCalibration x ColorMatrix(T)) * neutral, with the
                   ColorMatrix interpolated in 1/T between the two calibration illuminants (dng_color_spec);
  xy -> T, tint  : Robertson isotemperature lines in CIE 1960 uv, tint = distance along the line x -3000
                   (dng_temperature).
The probe checks this against the catalog on every "As Shot" photo (where Lightroom stored its own conversion).
Reads only the first IFD's tags; no pixels.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

# (mired, u, v, slope): Robertson's isotemperature lines, as used by the DNG SDK.
ROBERTSON = (
    (0, 0.18006, 0.26352, -0.24341), (10, 0.18066, 0.26589, -0.25479), (20, 0.18133, 0.26846, -0.26876),
    (30, 0.18208, 0.27119, -0.28539), (40, 0.18293, 0.27407, -0.30470), (50, 0.18388, 0.27709, -0.32675),
    (60, 0.18494, 0.28021, -0.35156), (70, 0.18611, 0.28342, -0.37915), (80, 0.18740, 0.28668, -0.40955),
    (90, 0.18880, 0.28997, -0.44278), (100, 0.19032, 0.29326, -0.47888), (125, 0.19462, 0.30141, -0.58204),
    (150, 0.19962, 0.30921, -0.70471), (175, 0.20525, 0.31647, -0.84901), (200, 0.21142, 0.32312, -1.0182),
    (225, 0.21807, 0.32909, -1.2168), (250, 0.22511, 0.33439, -1.4512), (275, 0.23247, 0.33904, -1.7298),
    (300, 0.24010, 0.34308, -2.0637), (325, 0.24702, 0.34655, -2.4681), (350, 0.25591, 0.34951, -2.9641),
    (375, 0.26400, 0.35200, -3.5814), (400, 0.27218, 0.35407, -4.3633), (425, 0.28039, 0.35577, -5.3762),
    (450, 0.28863, 0.35714, -6.7262), (475, 0.29685, 0.35823, -8.5955), (500, 0.30505, 0.35907, -11.324),
    (525, 0.31320, 0.35968, -15.628), (550, 0.32129, 0.36011, -23.325), (575, 0.32931, 0.36038, -40.770),
    (600, 0.33724, 0.36051, -116.45),
)
TINT_SCALE = -3000.0
ILLUMINANT_K = {17: 2856.0, 21: 6504.0, 20: 5503.0, 23: 5003.0, 1: 5500.0, 2: 3800.0, 3: 2856.0, 4: 5500.0,
                10: 6504.0, 11: 7504.0, 12: 6430.0, 13: 5000.0, 14: 4150.0, 15: 3450.0, 18: 4874.0, 19: 6774.0,
                22: 7504.0, 24: 3200.0}
D50_XY = (0.3457, 0.3585)
WB_TAGS = (50721, 50722, 50723, 50724, 50727, 50728, 50778, 50779, 50931, 50932)


def xy_to_temperature_tint(x: float, y: float) -> tuple[float, float]:
    """CIE xy -> (Kelvin, Lightroom tint), DNG SDK dng_temperature::Set_xy_coord."""
    u = 2.0 * x / (1.5 - x + 6.0 * y)
    v = 3.0 * y / (1.5 - x + 6.0 * y)
    last_dt = last_du = last_dv = 0.0
    for index in range(1, 31):
        du, dv = 1.0, ROBERTSON[index][3]
        length = math.hypot(du, dv)
        du, dv = du / length, dv / length
        uu, vv = u - ROBERTSON[index][1], v - ROBERTSON[index][2]
        dt = -uu * dv + vv * du
        if dt <= 0.0 or index == 30:
            dt = -min(dt, 0.0)
            f = 0.0 if index == 1 else dt / (last_dt + dt)
            temperature = 1.0e6 / (ROBERTSON[index - 1][0] * f + ROBERTSON[index][0] * (1.0 - f))
            uu = u - (ROBERTSON[index - 1][1] * f + ROBERTSON[index][1] * (1.0 - f))
            vv = v - (ROBERTSON[index - 1][2] * f + ROBERTSON[index][2] * (1.0 - f))
            du, dv = du * (1.0 - f) + last_du * f, dv * (1.0 - f) + last_dv * f
            length = math.hypot(du, dv)
            return temperature, (uu * du + vv * dv) / length * TINT_SCALE
        last_dt, last_du, last_dv = dt, du, dv
    raise ValueError("unreachable")


def _values(v) -> np.ndarray:
    return np.array(v, dtype=float).ravel()


def _rationals(v, n: int) -> np.ndarray:
    a = _values(v)
    return a[0::2] / np.where(a[1::2] == 0, 1, a[1::2]) if a.size == 2 * n else a


def read_wb_tags(path: Path) -> dict:
    """The white-balance-related DNG tags of a Smart Preview (first IFD)."""
    import tifffile

    with tifffile.TiffFile(str(path)) as tif:
        tags = tif.pages[0].tags
        return {code: tags[code].value for code in WB_TAGS if code in tags}


def as_shot_temperature_tint(tags: dict) -> tuple[float, float]:
    """(Kelvin, tint) of AsShotNeutral as Lightroom shows "As Shot". Raises ValueError if tags are missing."""
    if 50728 not in tags or 50721 not in tags:
        raise ValueError("AsShotNeutral or ColorMatrix1 missing")
    neutral = _rationals(tags[50728], 3)
    cm1 = _rationals(tags[50721], 9).reshape(3, 3)
    cm2 = _rationals(tags[50722], 9).reshape(3, 3) if 50722 in tags else cm1
    t1 = ILLUMINANT_K.get(int(_values(tags.get(50778, [17]))[0]), 2856.0)
    t2 = ILLUMINANT_K.get(int(_values(tags.get(50779, [21]))[0]), 6504.0)
    if t1 > t2:
        t1, t2, cm1, cm2 = t2, t1, cm2, cm1
    calibration = np.eye(3), np.eye(3)
    if 50723 in tags and str(tags.get(50931, "")) == str(tags.get(50932, "x")):
        cc1 = _rationals(tags[50723], 9).reshape(3, 3)
        calibration = cc1, (_rationals(tags[50724], 9).reshape(3, 3) if 50724 in tags else cc1)
    balance = np.diag(_rationals(tags[50727], 3)) if 50727 in tags else np.eye(3)

    def xyz_to_camera(xy: tuple[float, float]) -> np.ndarray:
        temperature, _tint = xy_to_temperature_tint(*xy)
        g = 1.0 if temperature <= t1 else 0.0 if temperature >= t2 else \
            (1.0 / temperature - 1.0 / t2) / (1.0 / t1 - 1.0 / t2)
        cm = g * cm1 + (1 - g) * cm2
        cc = g * calibration[0] + (1 - g) * calibration[1]
        return balance @ cc @ cm

    last = D50_XY
    for passes in range(30):
        xyz = np.linalg.solve(xyz_to_camera(last), neutral)
        total = float(xyz.sum())
        if total <= 0:
            raise ValueError("invalid neutral")
        nxt = (float(xyz[0] / total), float(xyz[1] / total))
        if abs(nxt[0] - last[0]) + abs(nxt[1] - last[1]) < 1e-7:
            last = nxt
            break
        last = ((last[0] + nxt[0]) / 2, (last[1] + nxt[1]) / 2) if passes == 29 else nxt
    return xy_to_temperature_tint(*last)
