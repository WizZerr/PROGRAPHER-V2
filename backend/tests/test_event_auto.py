"""Automatic event editing from a learning profile (as Imagen does), on synthetic catalogs only."""
from __future__ import annotations

import sqlite3
import time
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
    assert p["exposure"] == {"mode": "profile_level", "reason": "no_smart_previews", "level": -0.35,
                             "photos": 29, "analysed": 0}
    assert p["white_balance"] == "as_shot" and not p["blocking"]
    assert p["requires_acknowledgement"] == ["uniform_exposure"]  # one exposure for every photo: confirm it apart
    with pytest.raises(service.EventEditError, match="חשיפה אחידה"):
        service.confirm(plan["job_id"], wait=True)
    assert jobs.get(plan["job_id"])["status"] == "planned" and _digest(catalog) == before
    done = service.confirm(plan["job_id"], wait=True, acknowledged=["uniform_exposure"])
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


# --- matching Smart Previews (every photo, never a guess) and the uniform-exposure confirmation -------------------

def _previews(catalog: Path) -> Path:
    folder = catalog.with_name(f"{catalog.stem} Smart Previews.lrdata") / "A"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _exported_preview(folder: Path, names: dict[str, str], raw_name: str) -> Path:
    """A Smart Preview named by an id the catalog does not know (as after Export as Catalog), carrying its RAW name."""
    path = folder / f"EXPORTED-{len(names)}.dng"
    path.write_bytes(b"")
    names[path.name] = raw_name
    return path


def _match(catalog: Path, images) -> tuple[dict, dict]:
    from app.event_edit.scope import open_readonly

    job_id = jobs.create("complete", "e", catalog, [])
    db = open_readonly(catalog)
    try:
        return service._match_smart_previews(db, catalog.with_name(f"{catalog.stem} Smart Previews.lrdata"),
                                             sorted(images), job_id)
    finally:
        db.close()


def _rename_folder_files(catalog: Path, folder: str, like: str) -> None:
    """Give every file of `folder` the names of `like` (a second camera that numbers its files the same way)."""
    db = sqlite3.connect(catalog)
    db.execute("UPDATE AgLibraryFile SET baseName = REPLACE(baseName, ?, ?) WHERE folder = "
               "(SELECT id_local FROM AgLibraryFolder WHERE pathFromRoot = ?)", (folder, like, f"{folder}/"))
    db.commit()
    db.close()


def _faces_everywhere(monkeypatch, seen: list | None = None):
    from app.event_edit import exposure_target as et

    rgb = np.array([0.12, 0.09, 0.07])

    def measure(path):
        if seen is not None:
            seen.append(Path(path).name)
        return {"face_rgb": rgb, "face_stops": float(np.log2(rgb @ et.LUMA))}
    monkeypatch.setattr(et, "face_measurer", lambda long_edge=480: (measure, np.array([0]), None))
    monkeypatch.setattr(et, "solve_level", lambda faces, style, curve: (0.2, 0.0) if len(faces) >= 5 else None)
    monkeypatch.setattr(et, "automatic_exposures", lambda measured, style, curve: {i: 0.2 for i in measured})


def test_photos_left_by_the_ids_are_all_matched_by_raw_name_not_only_until_half(catalog: Path, monkeypatch):
    """20 of 30 photos matched by id used to stop the search (>= half): the other 10 must still be looked up."""
    from app.learning_intake import dng_diagnostics

    folder, names = _previews(catalog), {}
    event = _images_of(catalog, "EventA")
    for n, image in enumerate(event):
        if n < 20:
            (folder / f"UUID-{image}.dng").write_bytes(b"")
        elif n < 28:
            _exported_preview(folder, names, f"EventA_{n}.CR3")
    monkeypatch.setattr(dng_diagnostics, "read_original_raw_file_name", lambda p: names.get(Path(p).name))
    paths, stats = _match(catalog, event)
    assert stats == {"by_id": 20, "by_name": 8, "ambiguous": 0, "unmatched": 2}
    assert len(paths) == 28 and all(paths[i].name == f"UUID-{i}.dng" for i in event[:20])
    assert {paths[i].name for i in event[20:28]} == set(names)


def test_two_cameras_with_the_same_file_names_are_never_matched_by_name(catalog: Path, monkeypatch):
    """Camera B names its files like camera A. A name that more than one file in the catalog has is never used, and
    a Smart Preview that belongs to another photo (by id) is never handed to a photo by name."""
    from app.learning_intake import dng_diagnostics

    _rename_folder_files(catalog, "EventB", "EventA")  # EventB_0.CR3 ... -> EventA_0.CR3 ...
    folder, names = _previews(catalog), {}
    cam_a, cam_b = _images_of(catalog, "EventA"), _images_of(catalog, "EventB")
    for image in cam_a[:9]:
        (folder / f"UUID-{image}.dng").write_bytes(b"")  # camera A's own previews
    for n in range(9):
        _exported_preview(folder, names, f"EventA_{n}.CR3")  # previews carrying a name both cameras use
    names[f"UUID-{cam_a[0]}.dng"] = "EventA_0.CR3"
    monkeypatch.setattr(dng_diagnostics, "read_original_raw_file_name", lambda p: names.get(Path(p).name))
    paths, stats = _match(catalog, cam_a + cam_b)
    assert {i: p.name for i, p in paths.items()} == {i: f"UUID-{i}.dng" for i in cam_a[:9]}
    assert stats == {"by_id": 9, "by_name": 0, "ambiguous": 9, "unmatched": 21}  # camera B: all 9 ambiguous
    # The duplicate also counts when only one of the two files is in the chosen event.
    paths, stats = _match(catalog, cam_b)
    assert paths == {} and stats["ambiguous"] == 9


def test_a_raw_name_carried_by_two_smart_previews_is_not_guessed(catalog: Path, monkeypatch):
    from app.learning_intake import dng_diagnostics

    folder, names = _previews(catalog), {}
    event = _images_of(catalog, "EventA")
    _exported_preview(folder, names, "EventA_0.CR3")
    _exported_preview(folder, names, "EventA_0.cr3")  # e.g. a stale preview of a removed photo
    _exported_preview(folder, names, "EventA_1.CR3")
    monkeypatch.setattr(dng_diagnostics, "read_original_raw_file_name", lambda p: names.get(Path(p).name))
    paths, stats = _match(catalog, event)
    assert list(paths) == [event[1]] and stats["ambiguous"] == 1 and stats["unmatched"] == 28


def test_large_catalog_with_two_cameras_matches_only_the_unique_names(tmp_path: Path, monkeypatch):
    """Two cameras x 2,500 photos with identical names plus a third with 1,000 unique ones, all exported."""
    import time

    from app.learning_intake import dng_diagnostics

    (tmp_path / "big").mkdir()
    catalog = _build(tmp_path / "big" / "Big.lrcat", {"CamA": 2500, "CamB": 2500, "CamC": 1000})
    _rename_folder_files(catalog, "CamB", "CamA")
    folder, names = _previews(catalog), {}
    owner = {}
    for cam, count in (("CamA", 2500), ("CamC", 1000)):
        for n in range(count):
            owner[_exported_preview(folder, names, f"{cam}_{n}.CR3").name] = f"{cam}_{n}.CR3"
    monkeypatch.setattr(dng_diagnostics, "read_original_raw_file_name", lambda p: names.get(Path(p).name))
    images = _images_of(catalog, "CamA") + _images_of(catalog, "CamB") + _images_of(catalog, "CamC")
    start = time.monotonic()
    paths, stats = _match(catalog, images)
    assert time.monotonic() - start < 20
    assert stats == {"by_id": 0, "by_name": 1000, "ambiguous": 5000, "unmatched": 0}
    db = sqlite3.connect(catalog)
    file_name = dict(db.execute("SELECT i.id_local, f.baseName || '.' || f.extension FROM Adobe_images i "
                                "JOIN AgLibraryFile f ON f.id_local = i.rootFile"))
    db.close()
    assert all(owner[p.name] == file_name[i] for i, p in paths.items())  # every match is the photo's own file


def test_many_photos_without_analysis_need_the_uniform_exposure_confirmation(catalog: Path, profile: str,
                                                                              monkeypatch):
    folder = _previews(catalog)
    event = _images_of(catalog, "EventA")
    for image in event[:27]:  # 3 of 30 (10%) without a Smart Preview: a warning only
        (folder / f"UUID-{image}.dng").write_bytes(b"")
    _faces_everywhere(monkeypatch)
    plan = service.plan_automatic(catalog, _keys(catalog, "EventA"), profile, wait=True)["plan"]
    assert plan["exposure"]["mode"] == "faces" and plan["exposure"]["analysed"] == 27
    assert plan["warnings"] == [{"reason": "photos_without_analysis", "photos": 3, "of": 30}]
    assert plan["requires_acknowledgement"] == []
    (folder / f"UUID-{event[26]}.dng").unlink()  # 4 of 30 (13%): the uniform exposure must be confirmed apart
    job = service.plan_automatic(catalog, _keys(catalog, "EventA"), profile, wait=True)
    assert job["plan"]["requires_acknowledgement"] == ["uniform_exposure"]
    before = _digest(catalog)
    with pytest.raises(service.EventEditError):
        service.confirm(job["job_id"], wait=True, acknowledged=["something_else"])
    assert jobs.get(job["job_id"])["status"] == "planned" and _digest(catalog) == before
    assert service.confirm(job["job_id"], wait=True, acknowledged=["uniform_exposure"])["status"] == "completed"


def test_every_photo_analysed_needs_no_extra_confirmation(catalog: Path, profile: str, monkeypatch):
    folder = _previews(catalog)
    for image in _images_of(catalog, "EventA"):
        (folder / f"UUID-{image}.dng").write_bytes(b"")
    _faces_everywhere(monkeypatch)
    job = service.plan_automatic(catalog, _keys(catalog, "EventA"), profile, wait=True)
    assert job["plan"]["requires_acknowledgement"] == [] and job["plan"]["warnings"] == []
    assert job["plan"]["exposure"]["matching"] == {"by_id": 30, "by_name": 0, "ambiguous": 0, "unmatched": 0}
    assert service.confirm(job["job_id"], wait=True)["status"] == "completed"


@pytest.mark.parametrize("reason", ["face_model_missing", "too_few_faces_in_event"])
def test_no_face_analysis_means_uniform_exposure_and_its_own_confirmation(catalog: Path, profile: str,
                                                                         monkeypatch, reason: str):
    from app.event_edit import exposure_target as et

    folder = _previews(catalog)
    for image in _images_of(catalog, "EventA"):
        (folder / f"UUID-{image}.dng").write_bytes(b"")
    if reason == "face_model_missing":
        monkeypatch.setattr(et, "face_measurer", lambda long_edge=480: (None, None, "face_model_missing"))
    else:
        monkeypatch.setattr(et, "face_measurer", lambda long_edge=480: (lambda p: None, np.array([0]), None))
    plan = service.plan_automatic(catalog, _keys(catalog, "EventA"), profile, wait=True)["plan"]
    assert plan["exposure"]["mode"] == "profile_level" and plan["exposure"]["reason"] == reason
    assert plan["requires_acknowledgement"] == ["uniform_exposure"]
    assert plan["warnings"][0]["reason"] == "exposure_from_profile_level"


def test_api_confirm_needs_the_uniform_exposure_acknowledgement(catalog: Path, profile: str, monkeypatch):
    from fastapi.testclient import TestClient

    from app.application import create_app
    from tests.test_event_edit_api import HEADERS

    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", HEADERS["X-ProGrapher-Secret"])
    job = service.plan_automatic(catalog, _keys(catalog, "EventA"), profile, wait=True)
    url = f"/api/event-edit/jobs/{job['job_id']}/confirm"
    before = _digest(catalog)
    with TestClient(create_app()) as client:
        assert client.post(url, json={"confirm": True}, headers=HEADERS).status_code == 422
        assert client.post(url, json={"confirm": True, "acknowledge": ["anything"]}, headers=HEADERS).status_code == 422
        assert _digest(catalog) == before and jobs.get(job["job_id"])["status"] == "planned"
        ok = client.post(url, json={"confirm": True, "acknowledge": ["uniform_exposure"]}, headers=HEADERS)
        assert ok.status_code == 200
    for _ in range(200):
        if jobs.get(job["job_id"])["status"] == "completed":
            break
        time.sleep(0.02)
    assert jobs.get(job["job_id"])["status"] == "completed"
