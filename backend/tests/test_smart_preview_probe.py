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


# ---- stage 4: before / after pairs ----

def test_build_pairs_keeps_only_clean_linked_edits():
    from app.learning_intake.edit_pairs import build_pairs

    def link(status="linked_name_verified", virtual=False, **rec):
        base = {"file_stem": "img", "extension": "cr3", "catalog_root_name": "root", "catalog_folder": "shooter-a/",
                "capture_day": "2026-08-26", "develop": {"Exposure2012": 0.3, "Temperature": 5000.0, "Tint": 4.0,
                                                         "WhiteBalance": "Custom"},
                "complex": {}, "parse_exclusion": None, "pick": 0.0, "rating": None}
        base.update(rec)
        return {"record": base, "dng": Path("x.dng"), "status": status, "virtual_copy_candidate": virtual}

    links = [
        link(file_stem="good1"),
        link(file_stem="good2", catalog_folder="shooter-b/", develop={"Exposure2012": -0.5, "ConvertToGrayscale": True},
             complex={"ToneCurvePV2012": {"decoded": True, "is_linear": False}}, opaque_edit_review_required=True),
        link(file_stem="good3", develop={"Exposure2012": 0.5, "Temperature": 4000.0, "SaturationAdjustmentRed": -10.0,
                                         "Sharpness": 40.0, "ColorGradeBlending": 50.0}),
        link(file_stem="good4", catalog_folder="shooter-c/", develop={"Exposure2012": 0.1, "Sharpness": 40.0,
                                                                      "ColorGradeBlending": 50.0}),
        link(status="linked_name_mismatch"),
        link(virtual=True),
        link(parse_exclusion="missing_develop"),
        link(pick=-1.0),
        link(develop={"WhiteBalance": "As Shot"}),
    ]
    result = build_pairs(links)
    assert result["pairs_for_review"] == 4
    assert result["excluded_counts"] == {"link_not_verified": 1, "missing_develop": 1, "no_global_develop_values": 1,
                                         "rejected_in_lightroom": 1, "virtual_copy_shares_master_preview": 1}
    by_name = {p["file_name"]: p for p in result["pairs"]}
    assert by_name["good1.cr3"]["temperature_mired"] == 200.0
    assert "Dehaze" in by_name["good1.cr3"]["missing_targets"]  # absent stays absent, never zero
    assert by_name["good2.cr3"]["other_edits"] == {"tone_curve": True, "color_adjustments": False,
                                                   "local_or_opaque_edits": True, "black_and_white": True}
    assert by_name["good3.cr3"]["other_edits"]["color_adjustments"] is True
    assert by_name["good4.cr3"]["other_edits"]["color_adjustments"] is False  # sharpening / grading config only
    groups = {g["folder_group"]: g for g in result["folder_groups"]}
    assert groups["F01"]["pairs"] == 2 and groups["F01"]["exposure_median"] == 0.4  # shooter-a, largest first
    assert groups["F01"]["temperature_mired_median"] == 225.0
    # shooter-b has only a black & white photo: it is kept for review but is not part of the colour style numbers.
    assert groups["F02"]["pairs"] == 0 and groups["F02"]["exposure_median"] is None
    assert result["colour_pairs"] == 3
    assert result["target_coverage"]["Exposure2012"]["present"] == 3  # the black & white photo is left out
    assert result["target_coverage"]["Exposure2012"]["median"] == 0.3
    assert result["target_coverage"]["Dehaze"] == {"present": 0}
    assert "shooter" not in json.dumps({k: v for k, v in result.items() if k != "pairs"})


def test_black_and_white_is_flagged_from_the_settings_or_the_catalog_column():
    from app.learning_intake.edit_pairs import _other_edits

    assert _other_edits({"develop": {"ConvertToGrayscale": True}})["black_and_white"] is True
    assert _other_edits({"develop": {"Exposure2012": 0.2}, "grayscale": True})["black_and_white"] is True
    assert _other_edits({"develop": {"ConvertToGrayscale": False}, "grayscale": False})["black_and_white"] is False


def test_edit_pairs_api_returns_before_image_with_photographer_values(tmp_path, monkeypatch, fresh_decoder,
                                                                      jpegxl_codec, no_cached_look):
    from fastapi.testclient import TestClient
    from app.application import create_app
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", "pairs-test-secret")
    catalog = tmp_path / "Pilot.lrcat"
    catalog_fixture(catalog)  # one RAW photo 'photo.cr3' with Exposure2012=0.3
    smart = tmp_path / "Pilot Smart Previews.lrdata"
    (smart / "P").mkdir(parents=True)
    write_synthetic_smart_preview(smart / "P" / "p.dng", original_name="photo.cr3")
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding", color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    endpoint = f"/api/learning-intake/profiles/{owner['profile_id']}/edit-pairs"
    with TestClient(create_app()) as client:
        assert client.post(endpoint, json={"catalog_path": str(catalog)}).status_code == 401
        response = client.post(endpoint, json={"catalog_path": str(catalog)},
                               headers={"X-ProGrapher-Secret": "pairs-test-secret"})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["pairs_for_review"] == 1 and report["excluded_counts"] == {}
    sample = report["samples"][0]
    assert sample["file_name"] == "photo.cr3" and sample["targets"] == {"Exposure2012": 0.3}
    assert sample["folder_group"] == "F01"
    assert sample["reset_render"]["state"] == "reset_rendered_unverified"
    assert report["folder_groups"] == [{"folder_group": "F01", "pairs": 1, "exposure_median": 0.3,
                                        "temperature_mired_median": None, "tint_median": None}]
    assert report["training_ready_samples"] == 0
    assert str(smart) not in json.dumps(report) and "event" not in json.dumps(report["folder_groups"])


# ---- stage 5: anchor-method backtest ----

def _planck_xy(kelvin: float) -> tuple[float, float]:
    """Kim et al. cubic fit of the Planckian locus (independent of the Robertson table under test)."""
    t = kelvin
    x = (-3.0258469e9 / t**3 + 2.1070379e6 / t**2 + 0.2226347e3 / t + 0.240390 if t > 4000 else
         -0.2661239e9 / t**3 - 0.2343589e6 / t**2 + 0.8776956e3 / t + 0.179910)
    y = (3.0817580 * x**3 - 5.87338670 * x**2 + 3.75112997 * x - 0.37001483 if t > 4000 else
         -0.9549476 * x**3 - 1.37418593 * x**2 + 2.09137015 * x - 0.16748867)
    return x, y


def test_xy_to_lightroom_temperature_and_tint():
    from app.learning_intake.white_balance import xy_to_temperature_tint
    for kelvin in (3000, 5000, 6500, 9000):
        temperature, tint = xy_to_temperature_tint(*_planck_xy(kelvin))
        assert abs(temperature - kelvin) < 0.004 * kelvin and abs(tint) < 1.0
    temperature, tint = xy_to_temperature_tint(0.31271, 0.32902)  # D65: Lightroom shows about 6500 / +10
    assert abs(temperature - 6504) < 15 and 8 < tint < 12


def test_as_shot_neutral_to_temperature_and_tint():
    from app.learning_intake.white_balance import as_shot_temperature_tint

    def rat(values, den=10000):
        return [v for x in values for v in (int(round(x * den)), den)]

    x, y = _planck_xy(4200)
    xyz = [x / y, 1.0, (1 - x - y) / y]
    neutral = [v / xyz[1] for v in xyz]
    identity = [1, 0, 0, 0, 1, 0, 0, 0, 1]
    tags = {50721: rat(identity), 50722: rat(identity), 50778: 17, 50779: 21, 50728: rat(neutral, 1000000)}
    temperature, tint = as_shot_temperature_tint(tags)
    assert abs(temperature - 4200) < 25 and abs(tint) < 1.0
    # A camera calibration that boosts red makes the same raw neutral read cooler (the sensor saw less red).
    tags.update({50723: rat([1.1, 0, 0, 0, 1, 0, 0, 0, 1]), 50724: rat([1.1, 0, 0, 0, 1, 0, 0, 0, 1]),
                 50931: "com.adobe", 50932: "com.adobe"})
    assert as_shot_temperature_tint(tags)[0] > temperature + 100


def test_anchor_method_beats_baselines_when_edits_follow_time_runs():
    from app.learning_intake.anchor_backtest import predict, score
    rows = []
    for i in range(200):
        run = i // 40  # five lighting situations in time order, each edited consistently
        rows.append({"exposure": [-0.6, -0.2, 0.0, 0.3, -0.4][run], "d_mired": [-20, 0, 15, 5, -8][run],
                     "d_tint": [4, 0, -3, 2, 6][run], "as_shot_k": 4000 + 10 * i, "as_shot_tint": i % 7})
    run = predict(rows, 5)
    results = {name: score(preds) for name, preds in run["methods"].items()}
    assert results["anchors"]["untouched_pct"] == 100.0
    assert results["global_median"]["untouched_pct"] < 50 and results["as_shot"]["untouched_pct"] < 50
    assert results["anchors"]["photos"] == 195  # anchors themselves are not scored


def write_backtest_catalog(path: Path, photos: list[dict]):
    """Lightroom-like catalog with one folder of RAW photos carrying white balance edits."""
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE Adobe_images(id_local INTEGER PRIMARY KEY,id_global TEXT,rootFile INTEGER,fileFormat TEXT,captureTime TEXT,originalCaptureTime TEXT,masterImage INTEGER,copyName TEXT,pick REAL,rating REAL);
        CREATE TABLE AgLibraryFile(id_local INTEGER PRIMARY KEY,id_global TEXT,baseName TEXT,extension TEXT,folder INTEGER);
        CREATE TABLE AgLibraryFolder(id_local INTEGER PRIMARY KEY,rootFolder INTEGER,pathFromRoot TEXT);
        CREATE TABLE AgLibraryRootFolder(id_local INTEGER PRIMARY KEY,name TEXT);
        CREATE TABLE Adobe_imageDevelopSettings(id_local INTEGER PRIMARY KEY,image INTEGER,text TEXT,processVersion TEXT,whiteBalance TEXT,grayscale INTEGER);
        """)
        db.execute("INSERT INTO AgLibraryRootFolder VALUES(1,'test')")
        db.execute("INSERT INTO AgLibraryFolder VALUES(2,1,'event')")
        for i, photo in enumerate(photos):
            db.execute("INSERT INTO AgLibraryFile VALUES(?,?,?,?,2)", (100 + i, f"file{i}", photo["name"], "cr3"))
            db.execute("INSERT INTO Adobe_images VALUES(?,?,?,'RAW',?,NULL,NULL,NULL,0,NULL)",
                       (10 + i, photo["uuid"], 100 + i, f"2026-09-20T12:{i:02d}:00"))
            text = (f's={{ Exposure2012={photo["exposure"]}, Temperature={photo["kelvin"]}, Tint={photo["tint"]}, '
                    f'WhiteBalance="{photo["wb"]}" }}')
            db.execute("INSERT INTO Adobe_imageDevelopSettings VALUES(?,?,?,'15.4',?,0)",
                       (1000 + i, 10 + i, text, photo["wb"]))


def test_anchor_backtest_api_end_to_end(tmp_path, monkeypatch, fresh_decoder, jpegxl_codec, no_cached_look):
    from fastapi.testclient import TestClient
    from app.application import create_app
    from app.learning_intake.white_balance import as_shot_temperature_tint, read_wb_tags
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", "backtest-secret")
    smart = tmp_path / "Event Smart Previews.lrdata"
    (smart / "A").mkdir(parents=True)
    first = smart / "A" / "uuid0.dng"
    write_synthetic_smart_preview(first, original_name="img0.cr3")
    shot_k, shot_tint = as_shot_temperature_tint(read_wb_tags(first))
    photos = []
    for i in range(12):
        name, uuid = f"img{i}", f"uuid{i}"
        if i:
            write_synthetic_smart_preview(smart / "A" / f"{uuid}.dng", original_name=f"{name}.cr3")
        warm = i >= 6  # second half of the event: the photographer warmed the image and lowered exposure
        photos.append({"name": name, "uuid": uuid, "exposure": -0.5 if warm else 0.2,
                       "kelvin": round(1e6 / (1e6 / shot_k - 20)) if warm else round(shot_k),
                       "tint": round(shot_tint) + (5 if warm else 0), "wb": "Custom" if warm else "As Shot"})
    catalog = tmp_path / "Event.lrcat"
    write_backtest_catalog(catalog, photos)
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding", color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    endpoint = f"/api/learning-intake/profiles/{owner['profile_id']}/anchor-backtest"
    with TestClient(create_app()) as client:
        assert client.post(endpoint, json={"catalog_path": str(catalog)}).status_code == 401
        response = client.post(endpoint, json={"catalog_path": str(catalog), "anchors": 5, "sample_size": 2},
                               headers={"X-ProGrapher-Secret": "backtest-secret"})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["photos_in_backtest"] == 12 and report["anchors_used"] == 2
    assert report["as_shot_conversion_check"]["as_shot_photos"] == 6
    assert report["as_shot_conversion_check"]["median_abs_kelvin"] <= 1.0
    assert report["results"]["anchors"]["untouched_pct"] == 100.0
    assert report["results"]["as_shot"]["untouched_pct"] < 100.0
    assert [row["anchor_count"] for row in report["anchor_curve"]] == [2]  # the count, not the method's score
    assert report["anchor_curve"][0]["anchors"] == 100.0
    assert len(report["samples"]) == 2 and report["samples"][0]["reset_render"]["state"] == "reset_rendered_unverified"
    assert report["model_stored"] is False and report["training_ready_samples"] == 0
    assert str(smart) not in json.dumps(report)


# ---- photographer flow: one-step analysis stored with the profile ----

def test_analyze_catalog_one_step_summary_is_stored_without_images(tmp_path, monkeypatch, fresh_decoder,
                                                                   jpegxl_codec, no_cached_look):
    from fastapi.testclient import TestClient
    from app.application import create_app
    from app.learning_intake.white_balance import as_shot_temperature_tint, read_wb_tags
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", "analyze-secret")
    smart = tmp_path / "Event Smart Previews.lrdata"
    (smart / "A").mkdir(parents=True)
    photos = []
    for i in range(10):
        write_synthetic_smart_preview(smart / "A" / f"uuid{i}.dng", original_name=f"img{i}.cr3")
        if i == 0:
            shot_k, shot_tint = as_shot_temperature_tint(read_wb_tags(smart / "A" / "uuid0.dng"))
        photos.append({"name": f"img{i}", "uuid": f"uuid{i}", "exposure": -0.3 if i < 5 else 0.1,
                       "kelvin": round(shot_k), "tint": round(shot_tint), "wb": "As Shot"})
    catalog = tmp_path / "Event.lrcat"
    write_backtest_catalog(catalog, photos)
    store = LearningProfileStore()
    owner = store.create(name="Test", photography_type="wedding", color_mode="color", consent=True)
    store.attach_catalog(owner["profile_id"], catalog_path=str(catalog))
    endpoint = f"/api/learning-intake/profiles/{owner['profile_id']}/analyze"
    headers = {"X-ProGrapher-Secret": "analyze-secret"}
    with TestClient(create_app()) as client:
        assert client.post(endpoint, json={"catalog_path": str(catalog)}).status_code == 401
        response = client.post(endpoint, json={"catalog_path": str(catalog)}, headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()
        stored = client.get(f"/api/learning-intake/profiles/{owner['profile_id']}", headers=headers).json()
    summary = result["summary"]
    assert summary["photos"] == 10 and summary["linked"] == 10 and summary["pairs"] == 10
    assert summary["black_and_white_pairs"] == 0 and summary["schema"].endswith(".v2")
    style = {s["key"]: s["kind"] for s in summary["style"]}
    assert style["Exposure2012"] == "per_photo" and style["Tint"] == "fixed"
    assert summary["savings"]["anchors"] == 2 and summary["savings"]["untouched_pct"] == 100.0
    assert result["samples"] and result["samples"][0]["thumbnail_jpeg_base64"]
    assert stored["catalogs"][0]["analysis"] == summary and stored["catalogs"][0]["analyzed_at"]
    as_text = json.dumps(stored)
    assert "img0" not in as_text and "thumbnail" not in as_text  # numbers only are stored
    store.delete(owner["profile_id"])
    with sqlite3.connect(store.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM learning_intake_analysis").fetchone()[0] == 0


def test_style_marks_sliders_used_on_few_photos_as_rare():
    from app.learning_intake.catalog_analysis import _style
    coverage = {"Blacks2012": {"present": 100, "median": -13, "p10": -13, "p90": -13},
                "Dehaze": {"present": 1, "median": 19, "p10": 19, "p90": 19},
                "Contrast2012": {"present": 100, "median": 0, "p10": 0, "p90": 0},
                "Exposure2012": {"present": 100, "median": -0.3, "p10": -0.6, "p90": 0.0}}
    kinds = {s["key"]: s["kind"] for s in _style(coverage, 100)}
    assert kinds == {"Exposure2012": "per_photo", "Contrast2012": "untouched", "Blacks2012": "fixed", "Dehaze": "rare"}
