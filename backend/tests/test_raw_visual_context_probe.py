"""Synthetic-only tests for original-RAW-only linear scene-descriptor probe."""
import numpy as np
import pytest
from app.photographer.raw_visual_context_probe import (
    describe_linear_rgb, choose_sample,
)


def test_black_and_white_luminance_fractions():
    frame=np.zeros((10,10,3),dtype=np.float32)
    frame[5:,:,:]=1.0
    desc=describe_linear_rgb(frame)
    assert desc["fraction_luminance_below_0_03"]==0.5
    assert desc["fraction_decoded_rgb_any_channel_above_0_985"]==0.5
    assert desc["luminance_p50_linear"]==pytest.approx(0.5)
    assert desc["linear_mean_r"]==pytest.approx(0.5)


def test_out_of_range_and_nan_rejected():
    for value in (float("nan"),-0.1,1.1):
        frame=np.full((4,4,3),value,dtype=np.float32)
        with pytest.raises(ValueError):
            describe_linear_rgb(frame)


def test_sample_is_bounded_and_excludes_mac_metadata_and_jpeg(tmp_path):
    for name in ("A.CR3","B.CR3","C.CR3","._D.CR3","EDIT.JPG"):
        (tmp_path/name).write_bytes(b"fixture")
    selected=choose_sample(tmp_path,2)
    assert len(selected)==2
    assert selected[0].name=="A.CR3"
    assert selected[-1].name=="C.CR3"
    with pytest.raises(ValueError):
        choose_sample(tmp_path,13)
