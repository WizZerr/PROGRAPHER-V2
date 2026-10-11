"""Synthetic Adobe XMP parity research tests; no photographer material."""
from pathlib import Path
import pytest
from app.photographer.lightroom_adobe_xmp_comparison import (
    XMPReferenceError, compare_sample, xmp_curve, xmp_global_fields,
)

def fixture(tmp_path, exposure="-0.65", middle="61, 45"):
    xmp = tmp_path / "SYNTH.xmp"
    xmp.write_text(
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">'
        '<rdf:RDF><rdf:Description crs:Exposure2012="' + exposure + '" '
        'crs:ConvertToGrayscale="False">'
        '<crs:ToneCurvePV2012><rdf:Seq>'
        '<rdf:li>0, 0</rdf:li><rdf:li>' + middle + '</rdf:li>'
        '<rdf:li>255, 241</rdf:li></rdf:Seq></crs:ToneCurvePV2012>'
        '<crs:MaskGroupBasedCorrections><rdf:Seq><rdf:li>'
        '<rdf:Description crs:Blacks2012="777"/></rdf:li></rdf:Seq>'
        '</crs:MaskGroupBasedCorrections></rdf:Description>'
        '</rdf:RDF></x:xmpmeta>', encoding="utf-8")
    sample = {"file_stem": "SYNTH", "extension": "cr3",
              "develop": {"Exposure2012": -0.65, "ConvertToGrayscale": False,
                          "Blacks2012": -13},
              "curves_and_opaque_structures": {
                  "ToneCurvePV2012": {"decoded": True,
                      "points": [[0, 0], [61, 45], [255, 241]]}
              }}
    return {"samples": [sample]}, xmp

def test_valid_matches_and_absent_not_zero(tmp_path):
    plan, xmp = fixture(tmp_path)
    report = compare_sample(plan, xmp)
    assert report["result_counts"] == {"match": 3, "not_exported": 1}
    assert report["field_status"]["Blacks2012"] == "not_exported"
    assert "SYNTH" not in str(report)
    assert "777" not in str(report)

def test_different_curve_and_exposure(tmp_path):
    plan, xmp = fixture(tmp_path, "-0.75", "61, 46")
    report = compare_sample(plan, xmp)
    assert report["field_status"]["ToneCurvePV2012"] == "different"
    assert report["field_status"]["Exposure2012"] == "different"

def test_multiple_stems_rejected(tmp_path):
    plan, xmp = fixture(tmp_path)
    plan["samples"].append(dict(plan["samples"][0]))
    with pytest.raises(XMPReferenceError):
        compare_sample(plan, xmp)

def test_malformed_xmp_rejected(tmp_path):
    plan, xmp = fixture(tmp_path)
    xmp.write_text("<broken", encoding="utf-8")
    with pytest.raises(XMPReferenceError):
        compare_sample(plan, xmp)

def test_curve_parser_rejects_bad_order():
    assert xmp_curve(["0, 0", "61, 45", "255, 241"]) == ((0, 0), (61, 45), (255, 241))
    assert xmp_curve(["0, 0", "0, 45"]) is None
