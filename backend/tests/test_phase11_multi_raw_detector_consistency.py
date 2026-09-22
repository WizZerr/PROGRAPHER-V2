from __future__ import annotations

import pytest

from tools.phase11_multi_raw_detector_consistency import (
    _iou,
    _match_detections,
)


def _det(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    confidence: float,
) -> dict:
    return {
        "kind": "subject",
        "confidence": confidence,
        "box": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        },
    }


def test_iou_identical_box_is_one() -> None:
    box = {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}
    assert _iou(box, box) == pytest.approx(1.0, abs=1e-12)


def test_iou_disjoint_box_is_zero() -> None:
    a = {"x": 0.0, "y": 0.0, "width": 0.1, "height": 0.1}
    b = {"x": 0.8, "y": 0.8, "width": 0.1, "height": 0.1}
    assert _iou(a, b) == 0.0


def test_detection_match_accepts_small_numeric_drift() -> None:
    cpu = [_det(x=0.1, y=0.1, width=0.4, height=0.6, confidence=0.95)]
    cuda = [_det(x=0.1005, y=0.1005, width=0.399, height=0.599, confidence=0.947)]

    result = _match_detections(
        cpu,
        cuda,
        min_iou=0.98,
        max_confidence_diff=0.01,
    )

    assert result["consistent"] is True
    assert result["matches"][0]["iou"] >= 0.98


def test_detection_match_rejects_count_mismatch() -> None:
    cpu = [_det(x=0.1, y=0.1, width=0.4, height=0.6, confidence=0.95)]
    cuda = []

    result = _match_detections(
        cpu,
        cuda,
        min_iou=0.98,
        max_confidence_diff=0.01,
    )

    assert result["consistent"] is False
    assert result["reason"] == "count_mismatch"
