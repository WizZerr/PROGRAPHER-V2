"""Event flow safety on synthetic catalogs only (never a photographer's catalog).

Covers: several events in one catalog, photos outside the scope, too few anchors, the photographer's own collection,
undo after a later edit, concurrent writes, byte-identical dry runs, Lightroom open, failure in the middle and
recovery, and a second attempt after a completed write."""
from __future__ import annotations

import hashlib
import sqlite3
import zlib
from pathlib import Path

import pytest

from app.event_edit import jobs, service
from app.lightroom_bridge import catalog_writer as writer
from tests.test_lb02_catalog_writer import SETTINGS

ANCHORS_PER_EVENT = 20  # MIN_EDITED_ANCHORS: every planned anchor must be edited for the gate to open


def _blob(text: str) -> bytes:
    raw = text.encode()
    return len(raw).to_bytes(4, "big") + zlib.compress(raw)


@pytest.fixture(autouse=True)
def _private_data_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))


def _build(path: Path, events: dict[str, int]) -> Path:
    """One catalog, one folder per event; bursts of 3 photos 5 s apart, a minute between bursts (one moment per
    burst), all As Shot 5150 K."""
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE Adobe_variablesTable (id_local INTEGER PRIMARY KEY, id_global, name, value);
        INSERT INTO Adobe_variablesTable VALUES (1, 'v', 'Adobe_entityIDCounter', 50000.0);
        CREATE TABLE AgLibraryRootFolder (id_local INTEGER PRIMARY KEY, id_global, absolutePath, name);
        INSERT INTO AgLibraryRootFolder VALUES (1, 'ROOT-1', 'D:/Photos/', 'Photos');
        CREATE TABLE AgLibraryFolder (id_local INTEGER PRIMARY KEY, pathFromRoot, rootFolder);
        CREATE TABLE Adobe_images (id_local INTEGER PRIMARY KEY, id_global, rootFile, masterImage, captureTime,
            originalCaptureTime, touchCount, touchTime, colorLabels NOT NULL DEFAULT '');
        CREATE TABLE AgLibraryFile (id_local INTEGER PRIMARY KEY, baseName, extension, folder);
        CREATE TABLE Adobe_imageDevelopSettings (id_local INTEGER PRIMARY KEY, image, text, digest,
            historySettingsID, hasDevelopAdjustmentsEx, whiteBalance, processVersion);
        CREATE TABLE Adobe_libraryImageDevelopHistoryStep (id_local INTEGER PRIMARY KEY, id_global, dateCreated,
            digest, hasBigData, hasDevelopAdjustments, image, name, relValueString, text, valueString);
        CREATE TABLE AgLibraryCollection (id_local INTEGER PRIMARY KEY, creationId NOT NULL, genealogy NOT NULL,
            imageCount, name NOT NULL, parent INTEGER, systemOnly NOT NULL);
        CREATE TABLE AgLibraryCollectionImage (id_local INTEGER PRIMARY KEY, collection INTEGER NOT NULL,
            image INTEGER NOT NULL, pick NOT NULL, positionInCollection);
    """)
    image = 1000
    for n, (name, count) in enumerate(events.items(), start=1):
        db.execute("INSERT INTO AgLibraryFolder VALUES (?, ?, 1)", (n, f"{name}/"))
        for k in range(count):
            image += 1
            db.execute("INSERT INTO AgLibraryFile VALUES (?, ?, 'CR3', ?)", (image, f"{name}_{k}", n))
            minute, second = divmod(60 * (k // 3) + 5 * (k % 3), 60)
            hour, minute = divmod(minute, 60)
            db.execute("INSERT INTO Adobe_images VALUES (?, ?, ?, NULL, ?, NULL, 1, 0, '')",
                       (image, f"UUID-{image}", image, f"2026-0{n}-10T{10 + hour:02d}:{minute:02d}:{second:02d}"))
            db.execute("INSERT INTO Adobe_imageDevelopSettings VALUES (?, ?, ?, 'old', ?, -1, 'As Shot', '15.4')",
                       (image, image, SETTINGS, f"H{image}"))
            db.execute("INSERT INTO Adobe_libraryImageDevelopHistoryStep VALUES (?, ?, 1.0, 'old', 0, -1, ?, "
                       "'Import', NULL, ?, NULL)", (10000 + image, f"H{image}", image, _blob(SETTINGS)))
    db.commit()
    db.close()
    return path


@pytest.fixture
def catalog(tmp_path: Path) -> Path:
    (tmp_path / "catalog").mkdir()
    return _build(tmp_path / "catalog" / "Studio.lrcat", {"EventA": 60, "EventB": 30, "EventC": 30})


def _keys(catalog: Path, *names: str) -> list[str]:
    return [f["key"] for f in service.folders(catalog)["folders"] if any(f["label"].endswith(n) for n in names)]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(catalog: Path, images) -> list:
    db = sqlite3.connect(catalog)
    try:
        marks = ",".join("?" * len(images))
        return db.execute(f"SELECT i.id_local, i.colorLabels, s.text, s.digest, s.historySettingsID FROM Adobe_images i "
                          f"JOIN Adobe_imageDevelopSettings s ON s.image = i.id_local WHERE i.id_local IN ({marks}) "
                          f"ORDER BY i.id_local", list(images)).fetchall()
    finally:
        db.close()


def _images_of(catalog: Path, folder: str) -> list[int]:
    db = sqlite3.connect(catalog)
    try:
        return [r[0] for r in db.execute("SELECT f.id_local FROM AgLibraryFile f JOIN AgLibraryFolder fo ON "
                                         "fo.id_local = f.folder WHERE fo.pathFromRoot = ?", (f"{folder}/",))]
    finally:
        db.close()


def _edit(catalog: Path, image: int, **values) -> None:
    """What Lightroom does when the photographer edits: new settings text + a named History step."""
    db = sqlite3.connect(catalog)
    text = db.execute("SELECT text FROM Adobe_imageDevelopSettings WHERE image = ?", (image,)).fetchone()[0]
    new = writer.set_settings(text, values)
    db.execute("UPDATE Adobe_imageDevelopSettings SET text = ?, historySettingsID = ? WHERE image = ?",
               (new, f"LR-{image}-{len(values)}", image))
    db.execute("INSERT INTO Adobe_libraryImageDevelopHistoryStep (id_local, id_global, image, name, dateCreated, text) "
               "VALUES ((SELECT MAX(id_local) + 1 FROM Adobe_libraryImageDevelopHistoryStep), ?, ?, 'Exposure', 2.0, ?)",
               (f"LR-{image}-{len(values)}", image, _blob(new)))
    db.commit()
    db.close()


def _mark_and_edit(catalog: Path, keys: list[str], edit_count: int | None = None) -> dict:
    plan = service.plan_anchors(catalog, keys, anchor_count=ANCHORS_PER_EVENT, wait=True)
    assert plan["status"] == "planned", plan
    done = service.confirm(plan["job_id"], wait=True)
    assert done["status"] == "completed", done
    anchors = jobs.get(plan["job_id"])["plan"]["anchors"]
    for image in anchors[: edit_count if edit_count is not None else len(anchors)]:
        _edit(catalog, image, Exposure2012=0.5, Highlights2012=-30)
    return {"plan": plan, "anchors": anchors}


# 1 + 2: several events in one catalog; nothing outside the chosen event changes

def test_completing_event_a_leaves_b_and_c_untouched(catalog: Path):
    b_and_c = _images_of(catalog, "EventB") + _images_of(catalog, "EventC")
    before = _rows(catalog, b_and_c)
    keys = _keys(catalog, "EventA")
    _mark_and_edit(catalog, keys)
    plan = service.plan_completion(catalog, keys, wait=True)
    assert plan["status"] == "planned" and plan["plan"]["will_write"] > 0
    done = service.confirm(plan["job_id"], wait=True)
    assert done["status"] == "completed"
    assert _rows(catalog, b_and_c) == before
    a_images = set(_images_of(catalog, "EventA"))
    assert set(jobs.get(plan["job_id"])["plan"]["images"]) == a_images


def test_a_plan_holding_a_photo_of_another_event_is_refused(catalog: Path):
    keys = _keys(catalog, "EventA")
    _mark_and_edit(catalog, keys)
    plan = service.plan_completion(catalog, keys, wait=True)
    stored = jobs.get(plan["job_id"])["plan"]
    intruder = _images_of(catalog, "EventB")[0]
    stored["edits"][str(intruder)] = {"Exposure2012": 2.0}
    stored["history_ids"][str(intruder)] = "INTRUDER"
    jobs.update(plan["job_id"], plan=stored)
    before = _digest(catalog)
    done = service.confirm(plan["job_id"], wait=True)
    assert done["status"] == "failed" and "outside the event" in done["error"]
    assert _digest(catalog) == before


def test_no_scope_no_work(catalog: Path):
    with pytest.raises(service.EventEditError):
        service.plan_anchors(catalog, [])
    failed = service.plan_anchors(catalog, ["NOT-A-ROOT|Nowhere/"], wait=True)
    assert failed["status"] == "failed"


# 3: not enough edited anchors

def test_too_few_edited_anchors_block_the_completion(catalog: Path):
    keys = _keys(catalog, "EventA")
    _mark_and_edit(catalog, keys, edit_count=1)
    plan = service.plan_completion(catalog, keys, wait=True)
    assert plan["plan"]["blocking"][0]["reason"] == "too_few_edited_anchors"
    assert plan["plan"]["will_write"] == 2  # only the two other photos of the one edited anchor's moment
    before = _digest(catalog)
    with pytest.raises(service.EventEditError):
        service.confirm(plan["job_id"], wait=True)
    assert _digest(catalog) == before


# 4: the photographer's collection

def test_the_photographers_collection_is_not_touched(catalog: Path):
    db = sqlite3.connect(catalog)
    db.execute("INSERT INTO AgLibraryCollection VALUES (7, 'com.adobe.ag.library.collection', '/17', NULL, ?, NULL, 0)",
               (writer.ANCHOR_COLLECTION,))
    db.execute("INSERT INTO AgLibraryCollectionImage VALUES (8, 7, 1001, 0, NULL)")
    db.commit()
    db.close()
    keys = _keys(catalog, "EventB")
    _mark_and_edit(catalog, keys, edit_count=0)
    _mark_and_edit(catalog, keys, edit_count=0)  # choosing again is safe too
    db = sqlite3.connect(catalog)
    assert writer.collection_members(db, 7) == [1001]
    assert db.execute("SELECT name FROM AgLibraryCollection WHERE id_local = 7").fetchone()[0] == writer.ANCHOR_COLLECTION
    db.close()


# 5: undo after a later edit

def test_undo_keeps_an_edit_made_after_prographer(catalog: Path):
    keys = _keys(catalog, "EventB")
    _mark_and_edit(catalog, keys)
    plan = service.plan_completion(catalog, keys, wait=True)
    service.confirm(plan["job_id"], wait=True)
    written = jobs.get(plan["job_id"])["result"]["written_images"]
    later = written[0]
    _edit(catalog, later, Exposure2012=1.2)  # the photographer edits after ProGrapher
    undo = service.plan_undo(plan["job_id"], wait=True)
    assert undo["plan"]["will_revert"] == len(written) - 1 and undo["plan"]["kept"] == {"changed_after_prographer": 1}
    done = service.confirm(undo["job_id"], wait=True)
    assert done["status"] == "completed" and done["result"]["reverted"] == len(written) - 1
    assert writer.read_settings(_rows(catalog, [later])[0][2])["Exposure2012"] == "1.2"
    assert _rows(catalog, [written[1]])[0][2] == SETTINGS
    assert jobs.get(plan["job_id"])["status"] == "undone"
    with pytest.raises(service.EventEditError):  # the same completion cannot be undone twice
        service.plan_undo(plan["job_id"])


def test_only_the_latest_completion_can_be_undone(catalog: Path):
    keys = _keys(catalog, "EventB")
    _mark_and_edit(catalog, keys)
    first = service.plan_completion(catalog, keys, wait=True)
    service.confirm(first["job_id"], wait=True)
    for image in jobs.get(first["job_id"])["plan"]["images"][:3]:
        _edit(catalog, image, Exposure2012=0.1)
    second = service.plan_completion(catalog, keys, wait=True)
    jobs.update(second["job_id"], status="completed", result={"written_images": []})
    with pytest.raises(service.EventEditError, match="האחרונה"):
        service.plan_undo(first["job_id"])


# 6: two writes at once

def test_concurrent_write_on_the_same_catalog_is_refused(catalog: Path):
    keys = _keys(catalog, "EventC")
    _mark_and_edit(catalog, keys)
    plan = service.plan_completion(catalog, keys, wait=True)
    before = _digest(catalog)
    with writer.catalog_lock(catalog):  # another ProGrapher write holds the catalog
        done = service.confirm(plan["job_id"], wait=True)
    assert done["status"] == "failed" and "כבר מתבצעת" in done["error"]
    assert _digest(catalog) == before
    other = service.plan_completion(catalog, keys, wait=True)
    jobs.update(other["job_id"], status="writing")
    jobs._running.add(other["job_id"])
    try:
        again = service.plan_completion(catalog, keys, wait=True)
        with pytest.raises(service.EventEditError, match="כבר מתבצעת"):
            service.confirm(again["job_id"], wait=True)
    finally:
        jobs._running.discard(other["job_id"])


# 7: dry runs do not change a byte

def test_dry_runs_do_not_change_a_byte(catalog: Path):
    keys = _keys(catalog, "EventA")
    listing = sorted(p.name for p in catalog.parent.iterdir())
    before = _digest(catalog)
    service.folders(catalog)
    service.plan_anchors(catalog, keys, wait=True)
    assert _digest(catalog) == before and sorted(p.name for p in catalog.parent.iterdir()) == listing
    _mark_and_edit(catalog, keys)
    before = _digest(catalog)
    listing = sorted(p.name for p in catalog.parent.iterdir())
    plan = service.plan_completion(catalog, keys, wait=True)
    assert plan["status"] == "planned"
    assert _digest(catalog) == before and sorted(p.name for p in catalog.parent.iterdir()) == listing


def test_a_plan_is_refused_when_the_event_changed_since(catalog: Path):
    keys = _keys(catalog, "EventA")
    _mark_and_edit(catalog, keys)
    plan = service.plan_completion(catalog, keys, wait=True)
    _edit(catalog, _images_of(catalog, "EventA")[-1], Exposure2012=-0.4)  # edited after the dry run
    before = _digest(catalog)
    done = service.confirm(plan["job_id"], wait=True)
    assert done["status"] == "outdated"
    assert _digest(catalog) == before


# 8: Lightroom open

def test_lightroom_open_stops_planning_and_writing(catalog: Path, monkeypatch):
    keys = _keys(catalog, "EventA")
    _mark_and_edit(catalog, keys)
    plan = service.plan_completion(catalog, keys, wait=True)
    Path(f"{catalog}.lock").write_text("")
    with pytest.raises(service.EventEditError, match="Lightroom"):
        service.confirm(plan["job_id"], wait=True)
    with pytest.raises(service.EventEditError, match="Lightroom"):
        service.plan_completion(catalog, keys)
    Path(f"{catalog}.lock").unlink()
    before = _digest(catalog)
    monkeypatch.setattr(writer, "lightroom_lock_present", lambda _c: True)  # Lightroom opens during the write
    done = service.confirm(plan["job_id"], wait=True)
    assert done["status"] == "failed" and "Lightroom" in done["error"]
    assert _digest(catalog) == before


# 9: failure in the middle, crash recovery

def test_failure_in_the_middle_writes_nothing_and_can_be_planned_again(catalog: Path, monkeypatch):
    keys = _keys(catalog, "EventA")
    _mark_and_edit(catalog, keys)
    plan = service.plan_completion(catalog, keys, wait=True)
    before = _digest(catalog)
    real, seen = writer._encode_history, []

    def flaky(method, text):
        seen.append(1)
        if len(seen) == 3:
            raise RuntimeError("simulated crash")
        return real(method, text)
    monkeypatch.setattr(writer, "_encode_history", flaky)
    done = service.confirm(plan["job_id"], wait=True)
    assert done["status"] == "failed"
    assert _digest(catalog) == before
    monkeypatch.setattr(writer, "_encode_history", real)
    retry = service.plan_completion(catalog, keys, wait=True)
    assert service.confirm(retry["job_id"], wait=True)["status"] == "completed"


def test_a_job_left_writing_by_a_crash_is_recovered_from_the_catalog(catalog: Path):
    keys = _keys(catalog, "EventA")
    _mark_and_edit(catalog, keys)
    crashed = service.plan_completion(catalog, keys, wait=True)
    jobs.update(crashed["job_id"], status="writing")  # the process died before writing anything
    assert service.get_job(crashed["job_id"])["status"] == "failed"
    finished = service.plan_completion(catalog, keys, wait=True)
    service.confirm(finished["job_id"], wait=True)
    jobs.update(finished["job_id"], status="writing")  # the process died right after the commit
    assert service.get_job(finished["job_id"])["status"] == "completed"


# 10: trying again after a completed write

def test_a_completed_plan_cannot_run_twice_and_a_new_plan_has_nothing_left(catalog: Path):
    keys = _keys(catalog, "EventA")
    _mark_and_edit(catalog, keys)
    plan = service.plan_completion(catalog, keys, wait=True)
    assert service.confirm(plan["job_id"], wait=True)["status"] == "completed"
    with pytest.raises(service.EventEditError):
        service.confirm(plan["job_id"], wait=True)
    again = service.plan_completion(catalog, keys, wait=True)
    assert again["plan"]["will_write"] == 0
    assert again["plan"]["skipped"]["already_up_to_date"] == plan["plan"]["will_write"]


def test_plan_reports_what_it_would_write(catalog: Path):
    keys = _keys(catalog, "EventA")
    _mark_and_edit(catalog, keys)
    plan = service.plan_completion(catalog, keys, wait=True)["plan"]
    assert plan["sliders"] == ["Exposure2012", "Highlights2012"]
    assert plan["assessment"]["anchors_edited"] == ANCHORS_PER_EVENT
    assert plan["will_write"] == 60 - ANCHORS_PER_EVENT and plan["skipped"] == {}
    assert plan["backup_folder"].endswith("ProGrapher Backups")
    assert "edits" not in plan and "before" not in plan  # per-photo data stays private


def test_choosing_anchors_can_be_undone_without_touching_the_photographers_labels(catalog: Path):
    keys = _keys(catalog, "EventB")
    db = sqlite3.connect(catalog)
    db.execute("UPDATE Adobe_images SET colorLabels = 'Red' WHERE id_local = ?", (_images_of(catalog, "EventB")[1],))
    db.commit()
    db.close()
    before = _rows(catalog, _images_of(catalog, "EventB"))
    marked = _mark_and_edit(catalog, keys, edit_count=0)
    undo = service.plan_undo(marked["plan"]["job_id"], wait=True)
    assert undo["plan"]["collection_removable"] is True
    done = service.confirm(undo["job_id"], wait=True)
    assert done["status"] == "completed" and done["result"]["collection_removed"] is True
    assert _rows(catalog, _images_of(catalog, "EventB")) == before
    db = sqlite3.connect(catalog)
    assert db.execute("SELECT COUNT(*) FROM AgLibraryCollection").fetchone()[0] == 0
    db.close()


def test_cancel_only_before_writing(catalog: Path):
    keys = _keys(catalog, "EventA")
    plan = service.plan_anchors(catalog, keys, wait=True)
    assert service.cancel(plan["job_id"])["status"] == "cancelled"
    with pytest.raises(service.EventEditError):
        service.confirm(plan["job_id"], wait=True)
    other = service.plan_anchors(catalog, keys, wait=True)
    jobs.update(other["job_id"], status="writing")
    with pytest.raises(service.EventEditError):
        service.cancel(other["job_id"])


# regressions from the independent review of the write path

def test_cancel_during_planning_wins_over_the_finished_dry_run(catalog: Path, monkeypatch):
    keys = _keys(catalog, "EventA")
    real = service.read_photos

    def cancel_midway(db, images):
        latest = jobs.jobs_for_catalog(catalog.resolve(), ("planning",))[0]
        service.cancel(latest["job_id"])
        return real(db, images)
    monkeypatch.setattr(service, "read_photos", cancel_midway)
    plan = service.plan_anchors(catalog, keys, wait=True)
    assert plan["status"] == "cancelled"
    with pytest.raises(service.EventEditError):
        service.confirm(plan["job_id"], wait=True)


def test_removing_anchors_from_the_collection_does_not_lower_the_gate(catalog: Path):
    keys = _keys(catalog, "EventA")
    marked = _mark_and_edit(catalog, keys, edit_count=2)
    collection = jobs.get_event(jobs.get(marked["plan"]["job_id"])["event_id"])["collection_id"]
    db = sqlite3.connect(catalog)
    db.execute(f"DELETE FROM AgLibraryCollectionImage WHERE collection = ? AND image NOT IN "
               f"({','.join(map(str, marked['anchors'][:2]))})", (collection,))
    db.commit()
    db.close()
    plan = service.plan_completion(catalog, keys, wait=True)
    assert plan["plan"]["blocking"][0] == {"reason": "too_few_edited_anchors", "edited": 2, "required": 20}


def test_an_outdated_confirm_makes_no_backup(catalog: Path):
    keys = _keys(catalog, "EventA")
    _mark_and_edit(catalog, keys)
    plan = service.plan_completion(catalog, keys, wait=True)
    backups = catalog.parent / "ProGrapher Backups"
    count = len(list(backups.iterdir()))
    _edit(catalog, _images_of(catalog, "EventA")[1], Exposure2012=0.2)
    assert service.confirm(plan["job_id"], wait=True)["status"] == "outdated"
    assert len(list(backups.iterdir())) == count


def test_unmark_that_cannot_remove_the_collection_keeps_the_marking(catalog: Path):
    keys = _keys(catalog, "EventB")
    marked = _mark_and_edit(catalog, keys, edit_count=0)
    event = jobs.get_event(jobs.get(marked["plan"]["job_id"])["event_id"])
    db = sqlite3.connect(catalog)  # the photographer adds a photo to ProGrapher's collection
    db.execute("INSERT INTO AgLibraryCollectionImage VALUES (99999, ?, ?, 0, NULL)",
               (event["collection_id"], _images_of(catalog, "EventB")[0]))
    db.commit()
    db.close()
    undo = service.plan_undo(marked["plan"]["job_id"], wait=True)
    assert undo["plan"]["collection_removable"] is False
    assert service.confirm(undo["job_id"], wait=True)["status"] == "completed"
    assert jobs.get(marked["plan"]["job_id"])["status"] == "completed"
    assert jobs.get_event(event["event_id"])["collection_id"] == event["collection_id"]


def test_recovery_of_crashed_undo_and_anchor_jobs(catalog: Path):
    keys = _keys(catalog, "EventB")
    marked = _mark_and_edit(catalog, keys, edit_count=0)
    undo = service.plan_undo(marked["plan"]["job_id"], wait=True)
    jobs.update(undo["job_id"], status="writing")  # died before COMMIT: nothing removed
    assert service.get_job(undo["job_id"])["status"] == "failed"
    assert jobs.get(marked["plan"]["job_id"])["status"] == "completed"
    # the photographer changes ProGrapher's collection, so choosing again makes a new one; its name gets a "(2)"
    # suffix, and a crash right after COMMIT must still be recognised as written
    owned = jobs.get_event(jobs.get(marked["plan"]["job_id"])["event_id"])["collection_id"]
    db = sqlite3.connect(catalog)
    db.execute("INSERT INTO AgLibraryCollectionImage (collection, image, pick) VALUES (?, ?, 0)",
               (owned, _images_of(catalog, "EventB")[0]))
    db.commit()
    db.close()
    again = service.plan_anchors(catalog, keys, anchor_count=ANCHORS_PER_EVENT, wait=True)
    assert again["plan"]["reuse_collection"] is False
    stored = jobs.get(again["job_id"])
    db = sqlite3.connect(catalog)
    db.execute("INSERT INTO AgLibraryCollection VALUES (88888, 'com.adobe.ag.library.collection', '/588888', NULL, ?, "
               "NULL, 0)", (stored["plan"]["collection_name"] + " (2)",))
    db.executemany("INSERT INTO AgLibraryCollectionImage (collection, image, pick) VALUES (88888, ?, 0)",
                   [(i,) for i in stored["plan"]["anchors"]])
    db.commit()
    db.close()
    jobs.update(again["job_id"], status="writing")
    assert service.get_job(again["job_id"])["status"] == "completed"
    assert jobs.get_event(stored["event_id"])["collection_id"] == 88888


def test_recovery_reports_instead_of_crashing_when_the_catalog_is_unreadable(catalog: Path):
    keys = _keys(catalog, "EventA")
    _mark_and_edit(catalog, keys)
    plan = service.plan_completion(catalog, keys, wait=True)
    jobs.update(plan["job_id"], status="writing")
    catalog.write_bytes(b"not a database any more")
    job = service.get_job(plan["job_id"])
    assert job["status"] == "failed" and job["result"] == {"nothing_written": False}
