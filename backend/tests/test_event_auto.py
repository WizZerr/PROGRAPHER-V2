"""Automatic event editing from a learning profile (as Imagen does), on synthetic catalogs only."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from app.event_edit import jobs, service, style as event_style
from app.learning_intake.service import LearningProfileStore
from app.lightroom_bridge import catalog_writer as writer
from tests.test_event_edit_service import SETTINGS, _build, _digest, _edit, _images_of, _keys, _rows


@pytest.fixture(autouse=True)
def _private_data_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def catalog(tmp_path: Path) -> Path:
    (tmp_path / "catalog").mkdir()
    return _build(tmp_path / "catalog" / "Studio.lrcat", {"EventA": 30, "EventB": 9})


@pytest.fixture
def profile() -> str:
    store = LearningProfileStore()
    pid = store.create(name="Editor", photography_type="wedding", color_mode="color", consent=True)["profile_id"]
    store.save_style(pid, {"version": 1, "photos": 3000, "faces": 250, "white_balance": "as_shot",
                           "base": {"Highlights2012": -41, "Shadows2012": 18, "Texture": -18, "Clarity2012": -16},
                           "exposure_level": -0.35, "exposure_style": {"target_face_lightness": 53.3, "slope": -0.17}})
    return pid


def test_style_is_learnt_from_the_profiles_pairs():
    pairs = [{"dng": i, "targets": {"Exposure2012": -0.3 + 0.01 * (i % 3), "Texture": -18, "Clarity2012": -16,
                                     "Highlights2012": -40 - (i % 2)}} for i in range(60)]
    rng = np.random.default_rng(0)

    def measure(dng):
        rgb = np.array([0.12, 0.09, 0.07]) * 2 ** rng.normal(0, 0.4)
        return {"face_rgb": rgb, "face_stops": float(np.log2(rgb @ np.array([0.2126, 0.7152, 0.0722])))}
    curve = {"x": np.linspace(-14, 2, 200), "y": np.clip((np.linspace(-14, 2, 200) + 10) / 11, 0, 1) ** 0.8}
    style = event_style.learn(pairs, measure, curve)
    assert style["base"] == {"Highlights2012": -40.5, "Texture": -18, "Clarity2012": -16}
    assert style["exposure_level"] == pytest.approx(-0.29) and style["faces"] == 60
    assert style["exposure_style"] is not None and style["white_balance"] == "as_shot"
    without_faces = event_style.learn(pairs, None, None)
    assert without_faces["exposure_style"] is None and without_faces["exposure_level"] == pytest.approx(-0.29)


def test_whole_event_is_edited_automatically_without_anchors(catalog: Path, profile: str):
    b = _images_of(catalog, "EventB")
    before_b = _rows(catalog, b)
    keys = _keys(catalog, "EventA")
    mine = _images_of(catalog, "EventA")[0]
    _edit(catalog, mine, Exposure2012=1.0)  # the photographer already edited this one
    listing = sorted(p.name for p in catalog.parent.iterdir())
    before = _digest(catalog)
    plan = service.plan_automatic(catalog, keys, profile, wait=True)
    assert plan["status"] == "planned", plan
    assert _digest(catalog) == before and sorted(p.name for p in catalog.parent.iterdir()) == listing
    p = plan["plan"]
    assert p["will_write"] == 29 and p["skipped"] == {"edited_by_photographer": 1}
    assert p["sliders"] == ["Clarity2012", "Exposure2012", "Highlights2012", "Shadows2012", "Texture"]
    assert p["exposure"] == {"mode": "profile_level", "reason": "no_smart_previews", "level": -0.35}
    assert p["white_balance"] == "as_shot" and not p["blocking"]
    done = service.confirm(plan["job_id"], wait=True)
    assert done["status"] == "completed" and done["result"]["written"] == 29
    other = writer.read_settings(_rows(catalog, [_images_of(catalog, "EventA")[5]])[0][2])
    assert other["Exposure2012"] == "-0.35" and other["Highlights2012"] == "-41" and other["WhiteBalance"] == '"As Shot"'
    assert writer.read_settings(_rows(catalog, [mine])[0][2])["Exposure2012"] == "1"
    assert _rows(catalog, b) == before_b
    undo = service.plan_undo(plan["job_id"], wait=True)
    assert undo["plan"]["will_revert"] == 29
    assert service.confirm(undo["job_id"], wait=True)["status"] == "completed"
    assert _rows(catalog, [_images_of(catalog, "EventA")[5]])[0][2] == SETTINGS


def test_profile_without_anything_to_learn_is_reported(catalog: Path):
    pid = LearningProfileStore().create(name="Empty", photography_type="wedding", color_mode="color",
                                        consent=True)["profile_id"]
    plan = service.plan_automatic(catalog, _keys(catalog, "EventA"), pid, wait=True)
    assert plan["status"] == "failed" and "ללמוד" in plan["error"]
    with pytest.raises(service.EventEditError):
        service.plan_automatic(catalog, _keys(catalog, "EventA"), "no-such-profile")


def test_deleting_a_profile_removes_its_style(profile: str):
    store = LearningProfileStore()
    store.delete(profile)
    db = sqlite3.connect(store.db_path)
    assert db.execute("SELECT COUNT(*) FROM learning_intake_style").fetchone()[0] == 0
    db.close()


def test_exposure_follows_faces_when_the_event_has_smart_previews(catalog: Path, profile: str, monkeypatch):
    from app.event_edit import exposure_target as et

    previews = catalog.with_name("Studio Smart Previews.lrdata") / "A"
    previews.mkdir(parents=True)
    for image in _images_of(catalog, "EventA"):
        (previews / f"UUID-{image}.dng").write_bytes(b"")
    curve = {"x": np.linspace(-14, 2, 200), "y": np.clip((np.linspace(-14, 2, 200) + 10) / 11, 0, 1) ** 0.8}

    def measure(path):  # every other photo has a face one stop darker
        image = int(path.stem.split("-")[1])
        rgb = np.array([0.12, 0.09, 0.07]) * (0.5 if image % 2 else 1.0)
        return {"face_rgb": rgb, "face_stops": float(np.log2(rgb @ et.LUMA))}
    monkeypatch.setattr(et, "face_measurer", lambda long_edge=480: (measure, curve, None))
    plan = service.plan_automatic(catalog, _keys(catalog, "EventA"), profile, wait=True)
    assert plan["plan"]["exposure"]["mode"] == "faces" and plan["plan"]["exposure"]["faces"] == 30
    edits = jobs.get(plan["job_id"])["plan"]["edits"]
    darker = [v["Exposure2012"] for k, v in edits.items() if int(k) % 2]
    brighter = [v["Exposure2012"] for k, v in edits.items() if not int(k) % 2]
    assert len(set(darker)) == 1 and len(set(brighter)) == 1
    assert darker[0] - brighter[0] == pytest.approx(0.17, abs=0.02)  # slope -0.17 per stop of face


def test_smart_previews_of_an_exported_catalog_are_matched_by_raw_file_name(catalog: Path, profile: str, monkeypatch):
    """Export as Catalog gives photos new ids: the Smart Previews are found through the RAW name inside them."""
    from app.event_edit import exposure_target as et
    from app.learning_intake import dng_diagnostics

    previews = catalog.with_name("Studio Smart Previews.lrdata") / "A"
    previews.mkdir(parents=True)
    names = {}
    for n, image in enumerate(_images_of(catalog, "EventA")):
        path = previews / f"OTHER-UUID-{n}.dng"
        path.write_bytes(b"")
        names[path.name] = f"EventA_{n}.CR3"
    monkeypatch.setattr(dng_diagnostics, "read_original_raw_file_name", lambda p: names.get(Path(p).name))
    rgb = np.array([0.12, 0.09, 0.07])
    monkeypatch.setattr(et, "face_measurer", lambda long_edge=480: (
        lambda path: {"face_rgb": rgb, "face_stops": float(np.log2(rgb @ et.LUMA))}, np.array([0]), None))
    monkeypatch.setattr(et, "solve_level", lambda faces, style, curve: (0.2, 0.0) if len(faces) >= 5 else None)
    monkeypatch.setattr(et, "automatic_exposures", lambda measured, style, curve: {i: 0.2 for i in measured})
    plan = service.plan_automatic(catalog, _keys(catalog, "EventA"), profile, wait=True)
    exposure = plan["plan"]["exposure"]
    assert exposure["mode"] == "faces" and exposure["matched"] == 30 and exposure["measured"] == 30
