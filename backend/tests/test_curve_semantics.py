"""Synthetic tests: no photographer images, metadata or paths."""
import pytest

from app.photographer.curve_semantics import (
    decode_flat_point_curve,
    describe_curve,
)


def test_linear_curve_point_decoding():
    curve = decode_flat_point_curve('{ 0, 0, 255, 255 }')
    assert curve.points == ((0, 0), (255, 255))
    assert curve.is_linear is True
    metadata = describe_curve('{ 0, 0, 255, 255 }')
    assert metadata['decoded'] is True
    assert metadata['points'] == [[0, 0], [255, 255]]
    assert metadata['lightroom_semantics_validated'] is False


def test_non_linear_curve_with_intermediate_points():
    c = decode_flat_point_curve('{ 0,0, 64,40, 128,150, 255,255, }')
    assert len(c.points) == 4
    assert c.is_linear is False


@pytest.mark.parametrize('bad', [
    '{ 0,0, 255 }',
    '{ 255,255, 0,0 }',
    '{ 0,0, 0,10, 255,255 }',
    '{ 0,0, -1,10, 255,255 }',
    '{ 0,0, 255,256 }',
    '{ 0,0, 255, 2.5 }',
    '{ 0, 0, { 128, 128 }, 255, 255 }',
    '{ 0, 0, math.huge, 255 }',
    '{ 0, 0, 0/0, 255 }',
    '{ 0, 0, true, 255 }',
    '{ }',
])
def test_rejects_unsupported_shapes_without_fabricating_values(bad):
    metadata = describe_curve(bad)
    assert metadata['decoded'] is False
    assert 'undecoded_reason' in metadata
    assert 'points' not in metadata
    assert len(metadata['sha256']) == 64
