"""RAW-CAT-01D synthetic fixture regression; no private photographer data."""
from pathlib import Path
import json
import sqlite3
import pytest

from app.photographer.raw_catalog_intake import (
    CatalogIntakeError, inspect_catalog, parse_develop_settings, _write_atomic,
)


def synthetic_catalog(path: Path, *, duplicate: bool = False) -> None:
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE Adobe_images (id_local INTEGER PRIMARY KEY, id_global TEXT,
          rootFile INTEGER, fileFormat TEXT, captureTime TEXT, originalCaptureTime TEXT,
          masterImage INTEGER, copyName TEXT);
        CREATE TABLE AgLibraryFile (id_local INTEGER PRIMARY KEY, id_global TEXT,
          baseName TEXT, extension TEXT, folder INTEGER);
        CREATE TABLE AgLibraryFolder (id_local INTEGER PRIMARY KEY,
          rootFolder INTEGER, pathFromRoot TEXT);
        CREATE TABLE AgLibraryRootFolder (id_local INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE Adobe_imageDevelopSettings (id_local INTEGER PRIMARY KEY,
          image INTEGER, text TEXT, processVersion TEXT, whiteBalance TEXT, grayscale INTEGER);
        """)
        db.execute("INSERT INTO AgLibraryRootFolder VALUES(1, 'PRIVATE_DRIVE')")
        db.execute("INSERT INTO AgLibraryFolder VALUES(10, 1, 'PRIVATE_WEDDING')")
        db.executemany("INSERT INTO Adobe_images VALUES(?,?,?,?,?,?,?,?)", [
            (1, 'i1', 11, 'RAW', '2026-09-01 12:00', None, None, None),
            (2, 'i2', 12, 'RAW', '2026-09-01 12:02', None, None, None),
            (3, 'i3', 13, 'JPG', '2026-09-01 12:03', None, None, None),
        ])
        db.executemany("INSERT INTO AgLibraryFile VALUES(?,?,?,?,?)", [
            (11, 'f1', 'PRIVATE_001', 'cr3', 10),
            (12, 'f2', 'PRIVATE_002', 'cr3', 10),
            (13, 'f3', 'PRIVATE_003', 'jpg', 10),
        ])
        db.executemany("INSERT INTO Adobe_imageDevelopSettings VALUES(?,?,?,?,?,?)", [
            (21, 1, """s = { Exposure2012 = 0.75, CameraProfile = "Adobe, Standard",
                ConvertToGrayscale = true, ToneCurvePV2012 = { 0, 0, 255, 255 },
                ColorGradeGlobalSat = 20, Temperature = 5100, }""", '15.4', 'Custom', 1),
            (22, 2, 's = { Exposure2012=0, ConvertToGrayscale=false }', '15.4', 'As Shot', 0),
            (23, 3, 's = { Exposure2012=1 }', '15.4', 'Custom', 0),
        ])
        if duplicate:
            db.execute("INSERT INTO Adobe_imageDevelopSettings VALUES(?,?,?,?,?,?)", (24, 1, 's = {Exposure2012=2}', '15.4', 'Custom', 0))


def test_tokenizer_preserves_zero_and_nested_unknowns():
    d, curves, seen = parse_develop_settings('s={ Exposure2012=0, ToneCurvePV2012={ 0,0,255,255 }, Foo="hello, \\\"world\\\"", ConvertToGrayscale=false }')
    assert d['Exposure2012'] == 0
    assert d['ConvertToGrayscale'] is False
    # RAW-CAT-01E.01 now decodes supported, flat numeric point curves.
    assert curves['ToneCurvePV2012']['decoded'] is True
    assert curves['ToneCurvePV2012']['points'] == [[0, 0], [255, 255]]
    assert curves['ToneCurvePV2012']['lightroom_semantics_validated'] is False
    assert 'Foo' in seen and 'Foo' not in d
    with pytest.raises(ValueError):
        parse_develop_settings('s={ Exposure2012=nan }')
    with pytest.raises(ValueError):
        parse_develop_settings('s={ Exposure2012=1, Exposure2012=2 }')


def test_aggregate_privacy_and_candidate_grouping(tmp_path: Path):
    catalog = tmp_path/'test.lrcat'
    synthetic_catalog(catalog)
    report, private = inspect_catalog(catalog, include_private=True)
    assert report['totals']['catalog_photo_records'] == 3
    assert report['totals']['catalog_raw_records'] == 2
    assert report['totals']['parsed_raw_records'] == 2
    assert report['totals']['grayscale_raw_records'] == 1
    assert report['candidate_folder_day_groups'] == 1
    assert report['color_field_coverage']['ColorGradeGlobalSat'] == {'nonzero': 1, 'present': 1}
    assert report['training_ready_samples'] == 0
    assert private is not None and len(private['records']) == 2
    assert sorted(r['grayscale'] for r in private['records']) == [False, True]  # the editor's black & white photo
    assert {r['event_group_id'] for r in private['records']} == {'G0001'}
    assert all(not r['training_eligible'] and not r['source_raw_verified'] for r in private['records'])
    assert private['records'][0]['develop']['CameraProfile'] == 'Adobe, Standard'
    assert private['records'][0]['complex']['ToneCurvePV2012']['present']
    aggregate = json.dumps(report)
    assert 'PRIVATE_' not in aggregate and '2026-09-01' not in aggregate
    assert 'PRIVATE_001' in json.dumps(private)
    dest = tmp_path/'report.json'
    _write_atomic(dest, report)
    assert json.loads(dest.read_text())['totals']['parsed_raw_records'] == 2


def test_ambiguous_develop_is_quarantined_not_randomly_picked(tmp_path: Path):
    catalog = tmp_path/'dup.lrcat'
    synthetic_catalog(catalog, duplicate=True)
    report, private = inspect_catalog(catalog, include_private=True)
    assert report['totals']['catalog_raw_records'] == 2
    assert report['totals']['parsed_raw_records'] == 1
    assert report['exclusions']['ambiguous_develop_rows'] == 1
    assert private['records'][0]['status'] == 'quarantined'
    assert private['records'][0]['training_eligible'] is False


def test_bad_schema_fails_closed(tmp_path: Path):
    path = tmp_path/'bad.lrcat'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE Adobe_images (id_local INTEGER)')
    with pytest.raises(CatalogIntakeError, match='missing'):
        inspect_catalog(path)


def test_rejects_nonfinite_numeric_and_preserves_untouched_source(tmp_path: Path):
    path = tmp_path/'bad-num.lrcat'
    synthetic_catalog(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE Adobe_imageDevelopSettings SET text='s={Exposure2012=inf}' WHERE image=1")
    before = path.read_bytes()
    report, _ = inspect_catalog(path)
    assert report['exclusions']['develop_parse_failed'] == 1
    assert report['totals']['parsed_raw_records'] == 1
    assert path.read_bytes() == before

def test_01e_curve_coverage_is_aggregate_only_and_points_private(tmp_path: Path):
    catalog = tmp_path / 'curve.lrcat'
    synthetic_catalog(catalog)
    report, private = inspect_catalog(catalog, include_private=True)
    curve = report['curve_decode_coverage']['ToneCurvePV2012']
    assert curve == {'decoded': 1, 'linear': 1, 'present': 1}
    assert report['curve_decoder'].endswith('NOT Lightroom-validated')
    assert private['records'][0]['complex']['ToneCurvePV2012']['points'] == [[0, 0], [255, 255]]
    assert private['records'][0]['complex']['ToneCurvePV2012']['lightroom_semantics_validated'] is False
    assert '"points"' not in json.dumps(report)
    assert private['records'][0]['training_eligible'] is False


def test_01e_nested_unknown_curve_stays_undecoded_and_non_training(tmp_path: Path):
    catalog = tmp_path / 'nested.lrcat'
    synthetic_catalog(catalog)
    with sqlite3.connect(catalog) as db:
        db.execute(
            'UPDATE Adobe_imageDevelopSettings SET text=? WHERE image=1',
            ('s = { Exposure2012=0, ToneCurvePV2012={ x=1, y=2 } }',),
        )
    report, private = inspect_catalog(catalog, include_private=True)
    curve = report['curve_decode_coverage']['ToneCurvePV2012']
    assert curve['undecoded'] == 1
    assert curve['reason:unsupported_non_numeric_or_nested_curve'] == 1
    meta = private['records'][0]['complex']['ToneCurvePV2012']
    assert meta['decoded'] is False
    assert 'points' not in meta
    assert private['records'][0]['training_eligible'] is False


def test_flash_is_read_per_photo_when_lightroom_harvested_it(tmp_path: Path):
    catalog = tmp_path/'test.lrcat'
    synthetic_catalog(catalog)
    _report, private = inspect_catalog(catalog, include_private=True)
    assert [r['flash'] for r in private['records']] == [None, None]  # no EXIF table: unknown, never guessed
    with sqlite3.connect(catalog) as db:
        db.execute("CREATE TABLE AgHarvestedExifMetadata (id_local INTEGER PRIMARY KEY, image INTEGER, flashFired INTEGER)")
        db.executemany("INSERT INTO AgHarvestedExifMetadata VALUES(?,?,?)", [(31, 1, 1), (32, 2, 0)])
    report, private = inspect_catalog(catalog, include_private=True)
    assert {r['catalog_image_id']: r['flash'] for r in private['records']} == {1: True, 2: False}
    assert report['totals']['catalog_raw_records'] == 2
