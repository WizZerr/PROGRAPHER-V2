"""RAW-CAT-01E.02 synthetic data only: scalar color and opaque metadata."""
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from app.photographer.develop_color_semantics import (
    COLOR_FIELDS, COLOR_FAMILIES, describe_opaque_field, parse_color_scalar,
)
from app.photographer.raw_catalog_intake import inspect_catalog, parse_develop_settings
from test_raw_catalog_intake import synthetic_catalog


def test_hsl_grading_and_bw_controls_preserve_explicit_zeros():
    txt = ('s={ HueAdjustmentYellow=0, SaturationAdjustmentBlue=-18.5, '
           'LuminanceAdjustmentOrange=22, GrayMixerRed=-5, '
           'ColorGradeGlobalHue=225, ColorGradeShadowLum=0, '
           'ColorGradeBlending=50, SplitToningShadowHue=18 }')
    values, complex_items, seen = parse_develop_settings(txt)
    assert values['HueAdjustmentYellow'] == 0
    assert values['SaturationAdjustmentBlue'] == -18.5
    assert values['ColorGradeShadowLum'] == 0
    assert values['GrayMixerRed'] == -5
    assert values['SplitToningShadowHue'] == 18
    assert 'SaturationAdjustmentYellow' not in values
    assert set(values) == set(seen)
    assert not complex_items
    assert 'hsl_mixer' in COLOR_FAMILIES and 'HueAdjustmentYellow' in COLOR_FIELDS


@pytest.mark.parametrize('txt', [
    's={ColorGradeGlobalHue=nan}', 's={HueAdjustmentRed=inf}',
    's={SaturationAdjustmentBlue="x"}',
    's={GrayMixerBlue={20}}',
    's={ColorGradeBlending=-inf}',
])
def test_non_numeric_or_nested_color_is_rejected(txt):
    with pytest.raises(ValueError):
        parse_develop_settings(txt)


def test_opaque_mask_and_look_do_not_fake_interpretation():
    private_mark = 'customer-secret-look-001'
    serialized = f's={{ AILook={{ id="{private_mark}" }}, MaskGroupBasedCorrections={{ mask=1 }}, '
    serialized += 'PointColors={}, RetouchAreas="", CameraProfile="Custom Profile", '
    serialized += 'ColorGradeGlobalSat=0 }'
    values, complex_items, seen = parse_develop_settings(serialized)
    assert values['CameraProfile'] == 'Custom Profile'
    assert values['ColorGradeGlobalSat'] == 0
    assert complex_items['AILook']['decoded'] is False
    assert complex_items['MaskGroupBasedCorrections']['structure_nonempty'] is True
    assert complex_items['PointColors']['structure_nonempty'] is False
    assert complex_items['RetouchAreas']['structure_nonempty'] is False
    assert private_mark not in json.dumps(complex_items)
    assert hashlib.sha256('{}'.encode()).hexdigest() == complex_items['PointColors']['sha256']


def test_coverage_reporting_is_aggregate_only(tmp_path: Path):
    catalog = tmp_path / 'test.lrcat'
    synthetic_catalog(catalog)
    with sqlite3.connect(catalog) as db:
        db.execute('UPDATE Adobe_imageDevelopSettings SET text=? WHERE image=1', (
            's={HueAdjustmentRed=0, SaturationAdjustmentBlue=-2, '
            'ColorGradeGlobalSat=0, ColorGradeShadowLum=5, GrayMixerRed=10, '
            'Look={id="secret-private-uuid"}, MaskGroupBasedCorrections={item=1}, '
            'RetouchInfo={}}',))
    report, private = inspect_catalog(catalog, include_private=True)
    assert report['totals']['parsed_raw_records'] == 2
    assert report['color_field_coverage']['HueAdjustmentRed'] == {'explicit_zero': 1, 'present': 1}
    assert report['color_field_coverage']['SaturationAdjustmentBlue'] == {'nonzero': 1, 'present': 1}
    assert report['color_family_coverage']['hsl_mixer']['records_with_nonzero_field'] == 1
    assert report['opaque_local_edit_coverage']['MaskGroupBasedCorrections']['structure_nonempty'] == 1
    assert report['opaque_local_edit_coverage']['RetouchInfo']['structure_empty'] == 1
    assert report['profile_field_coverage']['Look']['opaque_not_decoded'] == 1
    assert 'secret-private-uuid' not in json.dumps(report)
    assert 'PRIVATE_' not in json.dumps(report)
    assert report['training_ready_samples'] == 0
    assert private['records'][0]['opaque_edit_review_required'] is True
    assert private['records'][1]['opaque_edit_review_required'] is False
    assert private['records'][0]['color_semantics_validated'] is False


def test_opaque_nested_empty_vs_present_and_not_edited_proof():
    d0 = describe_opaque_field('{ }', nested=True)
    d1 = describe_opaque_field('{ key=0 }', nested=True)
    assert d0['present'] and not d0['structure_nonempty']
    assert d1['present'] and d1['structure_nonempty']
    assert d1['decoded'] is False and d1['lightroom_semantics_validated'] is False



def test_grading_blending_nonzero_does_not_inflate_adjustment_count(tmp_path: Path):
    catalog = tmp_path / 'grading-defaults.lrcat'
    synthetic_catalog(catalog)
    with sqlite3.connect(catalog) as db:
        db.execute(
            'UPDATE Adobe_imageDevelopSettings SET text=? WHERE image=1',
            ('s={ColorGradeBlending=50, ColorGradeGlobalHue=0, '
             'ColorGradeGlobalSat=0, ColorGradeMidtoneLum=0}',),
        )
        db.execute(
            'UPDATE Adobe_imageDevelopSettings SET text=? WHERE image=2',
            ('s={ColorGradeBlending=50, ColorGradeGlobalSat=0, '
             'ColorGradeMidtoneSat=12}',),
        )
    report, private = inspect_catalog(catalog, include_private=True)
    counts = report['color_family_coverage']['color_grading']
    assert counts['records_with_field'] == 2
    assert counts['records_with_nonzero_field'] == 2
    assert counts['nonzero_configuration_values'] == 2
    assert counts['nonzero_adjustment_values'] == 1
    assert counts['records_with_nonzero_adjustment_candidate'] == 1
    assert private['records'][0]['training_eligible'] is False
    assert private['records'][1]['training_eligible'] is False
    assert 'PRIVATE_' not in json.dumps(report)
