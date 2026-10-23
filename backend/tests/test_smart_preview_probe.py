"""Read-only Smart Preview DNG probe tests; not proof of LR identity."""
from pathlib import Path
import json
import sqlite3

import pytest

from app.learning_intake.smart_preview_probe import inspect_smart_previews
from app.learning_intake import smart_preview_probe as probe
from app.learning_intake.service import LearningIntakeError, LearningProfileStore


def catalog_fixture(path: Path):
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE Adobe_images(id_local INTEGER PRIMARY KEY,id_global TEXT,rootFile INTEGER,fileFormat TEXT,captureTime TEXT,originalCaptureTime TEXT,masterImage INTEGER,copyName TEXT);
        CREATE TABLE AgLibraryFile(id_local INTEGER PRIMARY KEY,id_global TEXT,baseName TEXT,extension TEXT,folder INTEGER);
        CREATE TABLE AgLibraryFolder(id_local INTEGER PRIMARY KEY,rootFolder INTEGER,pathFromRoot TEXT);
        CREATE TABLE AgLibraryRootFolder(id_local INTEGER PRIMARY KEY,name TEXT);
        CREATE TABLE Adobe_imageDevelopSettings(id_local INTEGER PRIMARY KEY,image INTEGER,text TEXT,processVersion TEXT,whiteBalance TEXT,grayscale INTEGER);
        """)
        db.execute("INSERT INTO AgLibraryRootFolder VALUES(1,'test')")
        db.execute("INSERT INTO AgLibraryFolder VALUES(2,1,'event')")
        db.execute("INSERT INTO AgLibraryFile VALUES(3,'f','photo','cr3',2)")
        db.execute("INSERT INTO Adobe_images VALUES(5,'p',3,'RAW','2026-09-20',NULL,NULL,NULL)")
        db.execute("INSERT INTO Adobe_imageDevelopSettings VALUES(4,5,'s={ Exposure2012=0.3 }','15.4','As Shot',0)")


def test_smart_preview_dng_inventory_and_decode_is_not_identity(tmp_path, monkeypatch):
    root = tmp_path / "Test Smart Previews.lrdata"
    root.mkdir()
    (root / "a.dng").write_bytes(b"II*\\x00".replace(b"\\x00", b"\x00") + b"synthetic")
    (root / "bad.dng").write_bytes(b"wrong")
    (root / "cache.txt").write_text("test")
    monkeypatch.setattr(probe, "_decode_sample", lambda file: {
        "state": "decoded_unverified", "width": 2560, "height": 1707,
        "preview_mean_luma": 0.4,
    })
    report = inspect_smart_previews(root)
    assert report["counts"]["dng_tiff_signature_candidates"] == 1
    assert report["counts"]["invalid_dng_container_signature"] == 1
    assert report["decode_status_counts"]["decoded_unverified"] == 1
    assert report["training_ready_samples"] == 0
    assert not report["photo_to_dng_link_verified"]
    assert str(root) not in json.dumps(report)


def test_smart_preview_rejects_wrong_root_and_excessive_limit(tmp_path):
    wrong = tmp_path / "Ordinary Previews.lrdata"
    wrong.mkdir()
    with pytest.raises(LearningIntakeError, match="Smart Previews"):
        inspect_smart_previews(wrong)
    root = tmp_path / "Test Smart Previews.lrdata"
    root.mkdir()
    with pytest.raises(LearningIntakeError):
        inspect_smart_previews(root, decode_limit=5)


def test_scoped_profile_smart_preview_probe_and_api_auth(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.application import create_app
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", "preview-test-secret")
    catalog = tmp_path / "Pilot.lrcat"
    catalog_fixture(catalog)
    smart = tmp_path / "Pilot Smart Previews.lrdata"
    smart.mkdir()
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding", color_mode="color", consent=True)
    other = store.create(name="Other", photography_type="wedding", color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    with pytest.raises(LearningIntakeError, match="not linked"):
        store.probe_smart_previews(other["profile_id"], catalog_path=str(catalog))
    endpoint = f"/api/learning-intake/profiles/{owner['profile_id']}/smart-preview-probe"
    with TestClient(create_app()) as client:
        assert client.post(endpoint, json={"catalog_path": str(catalog)}).status_code == 401
        response = client.post(endpoint, json={"catalog_path": str(catalog)},
                               headers={"X-ProGrapher-Secret": "preview-test-secret"})
        assert response.status_code == 200, response.text
        assert response.json()["decode_attempts"] == 0
        assert response.json()["training_ready_samples"] == 0
        assert not response.json()["photo_to_dng_link_verified"]


def test_sdk_link_correlates_catalog_uuid_and_smart_dng_but_never_trains(tmp_path, monkeypatch):
    from app.learning_intake.sdk_link_review import verify_link_export
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "private"))
    catalog = tmp_path / "Pilot.lrcat"
    catalog_fixture(catalog)
    smart = tmp_path / "Pilot Smart Previews.lrdata"
    smart.mkdir()
    dng = smart / "sdk-generated-name.dng"
    dng.write_bytes(b"II*\x00" + b"synthetic")
    evidence = tmp_path / "sdk-links.json"
    evidence.write_text(json.dumps({
        "schema": "prographer.lightroom.smart_preview_sdk_links.v1",
        "catalog_path": str(catalog),
        "records": [{
            "photo_uuid": "p",
            "smart_preview_path": str(dng),
            "is_virtual_copy": False,
        }],
    }), encoding="utf-8")
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding",
                         color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    result = store.review_smart_preview_sdk_links(
        owner["profile_id"], catalog_path=str(catalog), evidence_path=str(evidence)
    )
    assert result["sdk_path_catalog_uuid_correlated"] == 1
    assert result["training_ready_samples"] == 0
    assert result["source_raw_identity_verified"] is False
    assert result["approved_finality_verified"] is False
    assert result["records"][0]["training_eligible"] is False


def test_sdk_link_rejects_foreign_paths_and_catalogs(tmp_path, monkeypatch):
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "private"))
    catalog = tmp_path / "Pilot.lrcat"
    catalog_fixture(catalog)
    smart = tmp_path / "Pilot Smart Previews.lrdata"
    smart.mkdir()
    foreign = tmp_path / "foreign.dng"
    foreign.write_bytes(b"II*\x00" + b"synthetic")
    evidence = tmp_path / "foreign.json"
    data = {
        "schema": "prographer.lightroom.smart_preview_sdk_links.v1",
        "catalog_path": str(catalog),
        "records": [{"photo_uuid": "p", "smart_preview_path": str(foreign)}],
    }
    evidence.write_text(json.dumps(data), encoding="utf-8")
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding",
                         color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    review = store.review_smart_preview_sdk_links(
        owner["profile_id"], catalog_path=str(catalog), evidence_path=str(evidence)
    )
    assert review["status_counts"]["outside_selected_smart_preview_root"] == 1
    assert review["sdk_path_catalog_uuid_correlated"] == 0
    data["catalog_path"] = str(tmp_path / "Other.lrcat")
    evidence.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(LearningIntakeError):
        store.review_smart_preview_sdk_links(
            owner["profile_id"], catalog_path=str(catalog), evidence_path=str(evidence)
        )


def test_sdk_link_duplicate_photo_uuid_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "private"))
    catalog = tmp_path / "Pilot.lrcat"
    catalog_fixture(catalog)
    smart = tmp_path / "Pilot Smart Previews.lrdata"
    smart.mkdir()
    evidence = tmp_path / "dupes.json"
    row = {"photo_uuid": "p", "smart_preview_path": None}
    evidence.write_text(json.dumps({
        "schema": "prographer.lightroom.smart_preview_sdk_links.v1",
        "catalog_path": str(catalog),
        "records": [row, row],
    }), encoding="utf-8")
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding",
                         color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    with pytest.raises(LearningIntakeError, match="Duplicate"):
        store.review_smart_preview_sdk_links(
            owner["profile_id"], catalog_path=str(catalog), evidence_path=str(evidence)
        )


def test_dng_diagnostics_detect_jpegxl_tag_without_decompressing(tmp_path):
    import struct
    from app.learning_intake.dng_diagnostics import inspect_dng_compression
    file = tmp_path / "private-raw.dng"
    # One classic TIFF IFD, with Compression=52546 stored directly in value.
    payload = (
        b"II*\x00" + struct.pack("<I", 8)
        + struct.pack("<H", 1)
        + struct.pack("<HHI", 259, 3, 1)
        + struct.pack("<H", 52546) + b"\x00\x00"
        + struct.pack("<I", 0)
    )
    file.write_bytes(payload)
    result = inspect_dng_compression(file)
    assert result["state"] == "tiff_ifd_read"
    assert result["compression_codes"] == [52546]


def test_jpegxl_route_uses_optional_source_only_decoder(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace, ModuleType
    import numpy as np
    from app.learning_intake.smart_preview_probe import _decode_sample
    from app.learning_intake import dng_diagnostics

    file = tmp_path / "real_photo_private.dng"
    file.write_bytes(b"II*\x00" + b"temporary placeholder")

    monkeypatch.setattr(dng_diagnostics, "inspect_dng_compression",
                        lambda _path: {"state": "tiff_ifd_read", "compression_codes": [52546]})
    module = ModuleType("smart_preview_decoder")
    class SmartPreviewError(Exception):
        pass
    module.SmartPreviewError = SmartPreviewError
    module.decode_smart_preview = lambda path, long_edge: SimpleNamespace(
        linear=np.full((40, 60, 3), 0.3, dtype=np.float32),
        compression=52546, opcodes_applied=["MapPolynomial"] * 3,
        opcodes_ignored=[], profile_name="Adobe Standard",
    )
    imagecodecs = ModuleType("imagecodecs")
    imagecodecs.JPEGXL = SimpleNamespace(available=True)
    from app.learning_intake import decoder_vendor
    monkeypatch.setattr(decoder_vendor, "load_decoder_package", lambda: module)
    monkeypatch.setitem(sys.modules, "imagecodecs", imagecodecs)

    result = _decode_sample(file)
    assert result["state"] == "jpegxl_dng_decoded_unverified"
    assert result["compression_code"] == 52546
    assert result["opcodes_applied"] == 3
    assert result["opcodes_ignored"] == 0
    assert result["width"] == 60 and result["height"] == 40
    assert "real_photo_private" not in str(result)


def test_jpegxl_unsupported_opcode_does_not_count_as_decoded(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace, ModuleType
    import numpy as np
    from app.learning_intake.smart_preview_probe import _decode_jpegxl_smart_preview

    file = tmp_path / "unsupported-opcode.dng"
    file.write_bytes(b"II*\x00" + b"test")
    module = ModuleType("smart_preview_decoder")
    module.SmartPreviewError = RuntimeError
    module.decode_smart_preview = lambda path, long_edge: SimpleNamespace(
        linear=np.ones((8, 8, 3), dtype=np.float32) * 0.5,
        compression=52546, opcodes_applied=["MapPolynomial"],
        opcodes_ignored=["UnrecognizedWarp"], profile_name=None,
    )
    imagecodecs = ModuleType("imagecodecs")
    imagecodecs.JPEGXL = SimpleNamespace(available=True)
    from app.learning_intake import decoder_vendor
    monkeypatch.setattr(decoder_vendor, "load_decoder_package", lambda: module)
    monkeypatch.setitem(sys.modules, "imagecodecs", imagecodecs)
    result = _decode_jpegxl_smart_preview(file)
    assert result["state"] == "jpegxl_dng_unhandled_opcodes"


def test_missing_optional_decoder_dependency_is_explicit(tmp_path, monkeypatch):
    import sys
    from app.learning_intake.smart_preview_probe import _decode_jpegxl_smart_preview
    file = tmp_path / "preview.dng"
    file.write_bytes(b"II*\x00")
    monkeypatch.setitem(sys.modules, "imagecodecs", None)
    result = _decode_jpegxl_smart_preview(file)
    assert result["state"] == "jpegxl_decoder_dependency_missing"
    assert result["compression_code"] == 52546


def test_bundled_decoder_source_is_verified_and_loadable_without_user_zip(
    tmp_path, monkeypatch,
):
    from app.learning_intake.decoder_vendor import (
        ARCHIVE, DECODER_SHA256, load_decoder_package,
    )
    import hashlib

    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "private_data"))
    assert ARCHIVE.is_file()
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == DECODER_SHA256
    imported = load_decoder_package()
    assert imported.__version__ == "1.0.0"
    assert callable(imported.decode_smart_preview)
    assert (tmp_path / "private_data" / "vendor_cache").is_dir()
    # Does not touch private source RAW, Lightroom catalog or DNG files.


def test_bundle_integrity_rejects_tampered_archive(tmp_path, monkeypatch):
    from app.learning_intake import decoder_vendor as vendor

    fake = tmp_path / "tampered.tar.xz"
    fake.write_bytes(b"changed source")
    monkeypatch.setattr(vendor, "ARCHIVE", fake)
    with pytest.raises(vendor.DecoderBundleError, match="checksum mismatch"):
        vendor.load_decoder_package()


# ---- real (unmocked) bundled decoder on a synthetic Lightroom-style Smart Preview ----

@pytest.fixture
def fresh_decoder(tmp_path, monkeypatch):
    """Isolated data dir and a clean import of the bundled decoder (other tests may have loaded it elsewhere)."""
    import sys
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "private_data"))
    monkeypatch.setattr(sys, "path", list(sys.path))
    for name in [m for m in sys.modules if m == "smart_preview_decoder" or m.startswith("smart_preview_decoder.")]:
        monkeypatch.delitem(sys.modules, name)
    yield


SYNTHETIC_COEF = [(0.001027, 0.062436, 0.0, 0.936537), (0.001865, 0.062383, 0.0, 0.935752),
                  (0.00079, 0.062451, 0.0, 0.936759)]  # cubic MapPolynomial per plane, as Lightroom writes


def write_synthetic_smart_preview(path: Path, h: int = 120, w: int = 180, original_name: str | None = None):
    """Lightroom layout: IFD0 = small RGB thumbnail whose SubIFD is the LinearRaw JPEG XL (52546) main image,
    with OpcodeList2 and an embedded camera profile. No real photo involved."""
    import struct
    import numpy as np
    tifffile = pytest.importorskip("tifffile")

    def rat(vals, den=10000):
        return [v for x in vals for v in (int(round(x * den)), den)]

    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[0:h, 0:w] / max(h, w)
    stored = (np.clip(np.stack([0.2 + 0.6 * xx, 0.3 + 0.5 * yy, 0.5 + 0.2 * xx * yy], -1)
                      + rng.normal(0, 0.01, (h, w, 3)), 0, 1) * 65535).astype(np.uint16)
    ops = struct.pack(">I", 3)
    for plane, coef in enumerate(SYNTHETIC_COEF):
        prm = struct.pack(">8I", 0, 0, h, w, plane, 1, 1, 1) + struct.pack(">I", 3) + struct.pack(">4d", *coef)
        ops += struct.pack(">IIII", 8, 0x01030000, 0, len(prm)) + prm
    matrix = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    dng_tags = [
        (50721, "2i", 9, rat(matrix), True), (50722, "2i", 9, rat(matrix), True),
        (50964, "2i", 9, rat([0.43, 0.39, 0.14, 0.18, 0.85, -0.03, 0.02, -0.25, 1.05]), True),
        (50965, "2i", 9, rat([0.45, 0.29, 0.22, 0.21, 0.78, 0.01, 0.03, -0.12, 0.92]), True),
        (50778, "H", 1, 17, True), (50779, "H", 1, 21, True),
        (50728, "2I", 3, rat([0.536126, 1.0, 0.6396], 1000000), True),
        (50730, "2i", 1, [136, 100], True), (50936, "s", 0, "Adobe Standard", True),
    ] + ([(50827, "s", 0, original_name, True)] if original_name else [])
    main_tags = [(50717, "I", 3, [65535] * 3, True), (50714, "2I", 3, [0, 1] * 3, True),
                 (51009, "B", 0, ops, True)]
    with tifffile.TiffWriter(path) as tif:
        tif.write(np.zeros((16, 24, 3), np.uint8), photometric="rgb", subifds=1, subfiletype=1,
                  extratags=dng_tags, metadata=None)
        tif.write(stored, photometric=34892, planarconfig="contig", compression="jpegxl_dng",
                  extratags=main_tags, metadata=None)
    return stored


def test_dng_diagnostics_follow_subifds_written_as_ifd_type(tmp_path):
    """SubIFDs (330) of TIFF type IFD (13) must be followed, or the JPEG XL image is never seen."""
    import struct
    from app.learning_intake.dng_diagnostics import inspect_dng_compression
    file = tmp_path / "subifd-type13.dng"
    ifd0 = 8
    ifd1 = ifd0 + 2 + 2 * 12 + 4
    payload = (b"II*\x00" + struct.pack("<I", ifd0) + struct.pack("<H", 2)
               + struct.pack("<HHI", 259, 3, 1) + struct.pack("<H", 1) + b"\x00\x00"
               + struct.pack("<HHI", 330, 13, 1) + struct.pack("<I", ifd1)
               + struct.pack("<I", 0)
               + struct.pack("<H", 1) + struct.pack("<HHI", 259, 3, 1) + struct.pack("<H", 52546) + b"\x00\x00"
               + struct.pack("<I", 0))
    file.write_bytes(payload)
    assert inspect_dng_compression(file)["compression_codes"] == [1, 52546]


def test_real_bundled_decoder_on_synthetic_jpegxl_smart_preview(tmp_path, fresh_decoder):
    """End to end, nothing mocked: SubIFD routing -> bundled decoder -> layer-1 linear pixels.
    Also checks the pinned tifffile/imagecodecs return the JPEG XL samples unchanged (the MapPolynomial must
    act on the stored values; a codec that converted them would break Lightroom parity)."""
    import numpy as np
    imagecodecs = pytest.importorskip("imagecodecs")
    if not getattr(getattr(imagecodecs, "JPEGXL", None), "available", False):
        pytest.skip("imagecodecs without JPEG XL")
    root = tmp_path / "Synthetic Smart Previews.lrdata"
    (root / "0").mkdir(parents=True)
    file = root / "0" / "PRIVATE-NAME-1234.dng"
    stored = write_synthetic_smart_preview(file)

    report = inspect_smart_previews(root, decode_limit=1)
    assert report["decode_status_counts"] == {"jpegxl_dng_decoded_unverified": 1}
    sample = report["decoded_samples"][0]
    assert sample["compression_code"] == 52546
    assert sample["opcodes_applied"] == 3 and sample["opcodes_ignored"] == 0
    assert sample["embedded_profile_present"] is True
    assert "PRIVATE-NAME" not in json.dumps(report) and str(root) not in json.dumps(report)
    assert report["training_ready_samples"] == 0

    from app.learning_intake.decoder_vendor import load_decoder_package
    sp = load_decoder_package().decode_smart_preview(file, long_edge=None)
    v = stored.astype(np.float64) / 65535.0
    expected = np.stack([np.clip(sum(c * v[..., p] ** k for k, c in enumerate(SYNTHETIC_COEF[p])), 0, 1)
                         for p in range(3)], -1)
    assert sp.linear.shape == expected.shape
    assert float(np.abs(sp.linear - expected).max()) < 1e-3
    assert abs(sp.baseline_exposure - 1.36) < 1e-9


def test_edited_decoder_cache_file_is_rebuilt_before_import(tmp_path, fresh_decoder):
    import hashlib
    from app.learning_intake import decoder_vendor as vendor
    vendor.load_decoder_package()
    cached = vendor._bundle_destination() / "smart_preview_decoder" / "dng.py"
    original = hashlib.sha256(cached.read_bytes()).hexdigest()
    cached.write_text("raise SystemExit('edited')\n", encoding="utf-8")
    vendor.load_decoder_package()
    assert hashlib.sha256(cached.read_bytes()).hexdigest() == original


# ---- layer 2-3: the unedited "before" image (Lightroom Reset look) ----

def write_look_xmp(path: Path, dims=(36, 8, 16)):
    """An Adobe-style profile .xmp holding a look table (crs:Table_: Adobe base85 of a zlib block). Neutral table."""
    import struct
    import zlib
    import numpy as np
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:+=^!/*?`'|()[]{}@%$#"
    table = np.tile(np.array([0.0, 1.0, 1.0], "<f4"), dims[0] * dims[1] * dims[2])
    raw = struct.pack("<5I", 1, 1, *dims) + table.tobytes()
    blob = struct.pack("<I", len(raw)) + zlib.compress(raw)
    out = []
    for i in range(0, len(blob), 4):
        chunk = blob[i:i + 4]
        v = struct.unpack("<I", chunk.ljust(4, b"\0"))[0]
        digits = []
        for _ in range(5):
            digits.append(alphabet[v % 85])
            v //= 85
        out.append("".join(digits if len(chunk) == 4 else digits[:len(chunk) + 1]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<x:xmpmeta><rdf:Description crs:Table_0123ABCD="{"".join(out)}"/></x:xmpmeta>', encoding="utf-8")


@pytest.fixture
def jpegxl_codec():
    imagecodecs = pytest.importorskip("imagecodecs")
    if not getattr(getattr(imagecodecs, "JPEGXL", None), "available", False):
        pytest.skip("imagecodecs without JPEG XL")


@pytest.fixture
def no_cached_look(tmp_path, monkeypatch):
    """No Adobe file of the machine running the tests is used: look only in the test data dir, lenses in tmp."""
    from app.learning_intake import smart_preview_render
    monkeypatch.setattr(smart_preview_render, "_found_look", {})
    monkeypatch.setattr(smart_preview_render, "_lens_files", {})
    monkeypatch.delenv("PROGRAPHER_ADOBE_COLOR_XMP", raising=False)
    monkeypatch.setattr(smart_preview_render, "look_search_roots",
                        lambda: [smart_preview_render.user_data_dir() / smart_preview_render.DROP_FOLDER])
    monkeypatch.setattr(smart_preview_render, "lens_search_roots", lambda: [tmp_path / "LensProfiles"])


def test_before_image_rendered_from_the_drop_folder_look(tmp_path, fresh_decoder, jpegxl_codec, no_cached_look):
    import base64
    import io
    from PIL import Image
    from app.platform.paths import user_data_dir
    write_look_xmp(user_data_dir() / "adobe_profiles" / "Adobe Color.xmp")
    root = tmp_path / "Synthetic Smart Previews.lrdata"
    root.mkdir()
    write_synthetic_smart_preview(root / "PRIVATE-NAME-5678.dng", h=300, w=900)

    report = inspect_smart_previews(root, decode_limit=1)
    render = report["decoded_samples"][0]["reset_render"]
    assert render["state"] == "reset_rendered_unverified"
    assert report["reset_render_counts"] == {"reset_rendered_unverified": 1}
    assert max(render["width"], render["height"]) == 512
    assert render["look_source"] == "adobe_color_xmp"
    assert render["lens_vignetting"] == "no_lens_metadata"
    assert render["calibration_stops"] == -0.144
    image = Image.open(io.BytesIO(base64.b64decode(render["thumbnail_jpeg_base64"])))
    assert image.format == "JPEG" and image.size == (render["width"], render["height"])
    assert 0.0 < render["mean_srgb_luma"] < 1.0
    assert report["training_ready_samples"] == 0
    assert "PRIVATE-NAME" not in json.dumps(report) and str(tmp_path) not in json.dumps(report)


def test_before_image_falls_back_to_the_smart_preview_look(tmp_path, fresh_decoder, jpegxl_codec, no_cached_look):
    """A customer whose Lightroom keeps Adobe Color somewhere unexpected still gets a 'before' image."""
    root = tmp_path / "Synthetic Smart Previews.lrdata"
    root.mkdir()
    write_synthetic_smart_preview(root / "a.dng")
    report = inspect_smart_previews(root, decode_limit=1)
    assert report["decode_status_counts"] == {"jpegxl_dng_decoded_unverified": 1}
    render = report["decoded_samples"][0]["reset_render"]
    assert render["state"] == "reset_rendered_unverified"
    assert render["look_source"] == "smart_preview_profile"


def write_lcp(path: Path, lens: str, k1: float = -0.8):
    """Minimal Adobe lens profile with one vignetting model (strong falloff, so the correction is visible)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/" '
        'xmlns:stCamera="http://ns.adobe.com/photoshop/1.0/camera-profile"><photoshop:CameraProfiles><rdf:Seq>'
        f'<rdf:li stCamera:Lens="{lens}" stCamera:FocalLength="50" stCamera:ApertureValue="2">'
        '<stCamera:PerspectiveModel stCamera:FocalLengthX="1.0">'
        f'<stCamera:VignetteModel stCamera:VignetteModelParam1="{k1}" stCamera:VignetteModelParam2="0" '
        'stCamera:VignetteModelParam3="0"/></stCamera:PerspectiveModel></rdf:li>'
        '</rdf:Seq></photoshop:CameraProfiles></rdf:Description></rdf:RDF></x:xmpmeta>', encoding="utf-8")


def test_before_image_applies_adobe_lens_vignetting(tmp_path, fresh_decoder, jpegxl_codec, no_cached_look,
                                                    monkeypatch):
    import base64
    import io
    import numpy as np
    from PIL import Image
    from app.learning_intake import smart_preview_render
    write_lcp(tmp_path / "LensProfiles" / "1.0" / "Test" / "Test Camera (Test Lens 50mm F2) - RAW.lcp",
              "Test Lens 50mm F2")
    root = tmp_path / "Synthetic Smart Previews.lrdata"
    root.mkdir()
    write_synthetic_smart_preview(root / "a.dng", h=200, w=300)

    def edge_vs_centre(report):
        img = np.asarray(Image.open(io.BytesIO(base64.b64decode(
            report["decoded_samples"][0]["reset_render"]["thumbnail_jpeg_base64"]))), dtype=float)
        h, w = img.shape[:2]
        return img[:h // 8].mean() + img[-h // 8:].mean(), report["decoded_samples"][0]["reset_render"]

    monkeypatch.setattr(smart_preview_render, "lens_exif", lambda _p: ("Other Lens 85mm", 50.0, 2.0))
    plain, render = edge_vs_centre(inspect_smart_previews(root, decode_limit=1))
    assert render["lens_vignetting"] == "lens_profile_not_found"
    monkeypatch.setattr(smart_preview_render, "lens_exif", lambda _p: ("Test Lens 50mm F2", 50.0, 2.0))
    corrected, render = edge_vs_centre(inspect_smart_previews(root, decode_limit=1))
    assert render["lens_vignetting"] == "applied"
    assert corrected > plain + 5  # light falloff corrected: the top and bottom rows get brighter
    assert "Test Lens" not in json.dumps(render)


def test_adobe_color_look_env_override_and_bad_file(tmp_path, fresh_decoder, no_cached_look, monkeypatch):
    from app.learning_intake.decoder_vendor import load_decoder_package
    from app.learning_intake.smart_preview_render import find_adobe_color_look
    decoder = load_decoder_package()
    bad = tmp_path / "not-a-look.xmp"
    bad.write_text("<x/>", encoding="utf-8")
    monkeypatch.setenv("PROGRAPHER_ADOBE_COLOR_XMP", str(bad))
    assert find_adobe_color_look(decoder) is None
    good = tmp_path / "look.xmp"
    write_look_xmp(good)
    monkeypatch.setenv("PROGRAPHER_ADOBE_COLOR_XMP", str(good))
    dims, table = find_adobe_color_look(decoder)
    assert tuple(dims) == (36, 8, 16) and table.size == 36 * 8 * 16 * 3


# ---- stage 3: catalog photo -> Smart Preview DNG links ----

def write_named_dng(path: Path, original_name: str | None, as_bytes: bool = False):
    """Tiny TIFF carrying only OriginalRawFileName (Lightroom writes it as BYTE or ASCII)."""
    import numpy as np
    tifffile = pytest.importorskip("tifffile")
    path.parent.mkdir(parents=True, exist_ok=True)
    tags = []
    if original_name is not None:
        data = original_name.encode() + b"\x00"
        tags = [(50827, "B", len(data), data, False)] if as_bytes else [(50827, "s", 0, original_name, False)]
    tifffile.imwrite(path, np.zeros((4, 4, 3), np.uint8), photometric="rgb", extratags=tags, metadata=None)


def test_read_original_raw_file_name(tmp_path):
    from app.learning_intake.dng_diagnostics import read_original_raw_file_name
    write_named_dng(tmp_path / "a.dng", "0H1A3976.CR3")
    write_named_dng(tmp_path / "b.dng", "DSC_0089.NEF", as_bytes=True)
    write_named_dng(tmp_path / "c.dng", None)
    (tmp_path / "d.dng").write_bytes(b"II*\x00" + b"\xff" * 12)
    assert read_original_raw_file_name(tmp_path / "a.dng") == "0H1A3976.CR3"
    assert read_original_raw_file_name(tmp_path / "b.dng") == "DSC_0089.NEF"
    assert read_original_raw_file_name(tmp_path / "c.dng") is None
    assert read_original_raw_file_name(tmp_path / "d.dng") is None


def test_build_links_statuses(tmp_path):
    from app.learning_intake.smart_preview_link import build_links
    root = tmp_path / "Test Smart Previews.lrdata"
    files = {
        "A": ("A/AAAA-IMG.dng", "a.cr3"), "B": ("B/BBBB-IMG.dng", "renamed.cr3"),
        "C": ("C/CCCC-FILE.dng", "c.cr3"), "N": ("N/NNNN-IMG.dng", None),
        "D1": ("D/DUP.dng", "d.cr3"), "D2": ("E/DUP.dng", "d.cr3"), "O": ("O/ORPHAN.dng", "o.cr3"),
    }
    for rel, name in files.values():
        write_named_dng(root / rel, name)
    dngs = sorted(root.rglob("*.dng"))

    def rec(image_id, file_id, stem, virtual=False):
        return {"catalog_global_image_id": image_id, "catalog_global_file_id": file_id,
                "file_stem": stem, "extension": "cr3", "virtual_copy_candidate": virtual}

    records = [rec("aaaa-img", "x1", "a"), rec("BBBB-IMG", "x2", "b"),
               rec("master-c", "CCCC-FILE", "c"), rec("vcopy-c", "CCCC-FILE", "c", virtual=True),
               rec("NNNN-IMG", "x4", "n"), rec("DUP", "x5", "d"), rec("missing", "x6", "m")]
    result = build_links(dngs, records)
    status = {l["record"]["catalog_global_image_id"]: l["status"] for l in result["links"]}
    assert status == {"aaaa-img": "linked_name_verified", "BBBB-IMG": "linked_name_mismatch",
                      "master-c": "linked_name_verified", "vcopy-c": "linked_name_verified",
                      "NNNN-IMG": "linked_name_unreadable", "DUP": "ambiguous_smart_preview",
                      "missing": "no_smart_preview"}
    assert result["matched_by_counts"] == {"file_uuid": 2, "image_uuid": 4}
    assert result["virtual_copy_records"] == 1
    assert result["records_sharing_a_preview"] == 2  # master and virtual copy: one 'before' image
    assert result["orphan_smart_previews"] == 3  # ORPHAN.dng and the two ambiguous DUP.dng


def test_smart_preview_links_api_shows_named_before_image(tmp_path, monkeypatch, fresh_decoder, jpegxl_codec,
                                                          no_cached_look):
    from fastapi.testclient import TestClient
    from app.application import create_app
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", "link-test-secret")
    catalog = tmp_path / "Pilot.lrcat"
    catalog_fixture(catalog)
    smart = tmp_path / "Pilot Smart Previews.lrdata"
    (smart / "P").mkdir(parents=True)
    write_synthetic_smart_preview(smart / "P" / "p.dng", original_name="photo.cr3")  # Adobe_images.id_global 'p'
    write_named_dng(smart / "Z" / "unrelated.dng", "other.cr3")
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding", color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    endpoint = f"/api/learning-intake/profiles/{owner['profile_id']}/smart-preview-links"
    with TestClient(create_app()) as client:
        assert client.post(endpoint, json={"catalog_path": str(catalog)}).status_code == 401
        response = client.post(endpoint, json={"catalog_path": str(catalog)},
                               headers={"X-ProGrapher-Secret": "link-test-secret"})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["catalog_raw_records"] == 1 and report["smart_preview_files"] == 2
    assert report["linked_name_verified"] == 1 and report["orphan_smart_previews"] == 1
    assert report["matched_by_counts"] == {"image_uuid": 1}
    sample = report["samples"][0]
    assert sample["file_name"] == "photo.cr3" and sample["link_status"] == "linked_name_verified"
    assert sample["decode_state"] == "jpegxl_dng_decoded_unverified"
    assert sample["reset_render"]["state"] == "reset_rendered_unverified"
    assert report["training_ready_samples"] == 0
    assert str(smart) not in json.dumps(report)
