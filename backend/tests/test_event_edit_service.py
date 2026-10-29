"""Event flow v1 end to end on a synthetic catalog: choose anchors, 'photographer' edits them, complete, undo."""
from __future__ import annotations

import sqlite3
import zlib
from pathlib import Path

import pytest

from app.event_edit import service
from app.lightroom_bridge import catalog_writer as writer
from tests.test_lb02_catalog_writer import SETTINGS


def _blob(text: str) -> bytes:
    raw = text.encode()
    return len(raw).to_bytes(4, "big") + zlib.compress(raw)


@pytest.fixture
def event(tmp_path: Path) -> Path:
    path = tmp_path / "Wedding.lrcat"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE Adobe_variablesTable (id_local INTEGER PRIMARY KEY, id_global, name, value);
        INSERT INTO Adobe_variablesTable VALUES (1, 'v', 'Adobe_entityIDCounter', 5000.0);
        CREATE TABLE Adobe_images (id_local INTEGER PRIMARY KEY, id_global, rootFile, masterImage, captureTime,
            originalCaptureTime, touchCount, touchTime, colorLabels NOT NULL DEFAULT '');
        CREATE TABLE AgLibraryFile (id_local INTEGER PRIMARY KEY, baseName, extension);
        CREATE TABLE Adobe_imageDevelopSettings (id_local INTEGER PRIMARY KEY, image, text, digest,
            historySettingsID, hasDevelopAdjustmentsEx, whiteBalance, processVersion);
        CREATE TABLE Adobe_libraryImageDevelopHistoryStep (id_local INTEGER PRIMARY KEY, id_global, dateCreated,
            digest, hasBigData, hasDevelopAdjustments, image, name, relValueString, text, valueString);
        CREATE TABLE AgLibraryCollection (id_local INTEGER PRIMARY KEY, creationId NOT NULL, genealogy NOT NULL,
            imageCount, name NOT NULL, parent INTEGER, systemOnly NOT NULL);
        CREATE TABLE AgLibraryCollectionImage (id_local INTEGER PRIMARY KEY, collection INTEGER NOT NULL,
            image INTEGER NOT NULL, pick NOT NULL, positionInCollection);
    """)
    # three moments: 10 photos at 18:00, 6 at 19:00, 2 at 20:00 (one photo every 5 s)
    image = 100
    for hour, count in ((18, 10), (19, 6), (20, 2)):
        for k in range(count):
            image += 1
            db.execute("INSERT INTO AgLibraryFile VALUES (?, ?, 'CR3')", (image, f"IMG_{image}"))
            db.execute("INSERT INTO Adobe_images VALUES (?, ?, ?, NULL, ?, NULL, 1, 0, '')",
                       (image, f"UUID-{image}", image, f"2026-08-26T{hour}:00:{5 * k:02d}"))
            db.execute("INSERT INTO Adobe_imageDevelopSettings VALUES (?, ?, ?, 'old', ?, -1, 'As Shot', '15.4')",
                       (image, image, SETTINGS, f"H{image}"))
            db.execute("INSERT INTO Adobe_libraryImageDevelopHistoryStep VALUES (?, ?, 1.0, 'old', 0, -1, ?, "
                       "'Import (26/08/2026)', NULL, ?, NULL)", (1000 + image, f"H{image}", image, _blob(SETTINGS)))
    db.commit()
    db.close()
    return path


def _edit_like_photographer(catalog: Path, image: int, **values):
    """What Lightroom does when the photographer edits: new settings text + a named History step."""
    db = sqlite3.connect(catalog)
    text = db.execute("SELECT text FROM Adobe_imageDevelopSettings WHERE image = ?", (image,)).fetchone()[0]
    new = writer.set_settings(text, values)
    db.execute("UPDATE Adobe_imageDevelopSettings SET text = ? WHERE image = ?", (new, image))
    db.execute("INSERT INTO Adobe_libraryImageDevelopHistoryStep (id_local, image, name, dateCreated, text) "
               "VALUES (?, ?, 'Exposure', 2.0, ?)", (3000 + image, image, _blob(new)))
    db.commit()
    db.close()


def _values(catalog: Path, image: int) -> dict:
    db = sqlite3.connect(catalog)
    text = db.execute("SELECT text FROM Adobe_imageDevelopSettings WHERE image = ?", (image,)).fetchone()[0]
    db.close()
    return writer.read_settings(text)


def test_event_flow_end_to_end(event: Path):
    plan = service.plan_anchors(event, anchor_count=2)
    assert plan["photos"] == 18 and plan["moments"] == 3 and plan["anchors"] == 2
    anchors = service.anchor_ids(event)
    assert anchors == [106, 114]  # middle photo of the two biggest moments
    assert plan["photos_in_anchored_moments"] == 16

    with pytest.raises(service.EventEditError):  # nothing edited yet
        service.complete(event, automatic_exposure=False)
    _edit_like_photographer(event, 106, Exposure2012=0.5, Highlights2012=-30, WhiteBalance="Custom",
                            Temperature=4800, Tint=10, CustomTemperature=4800, CustomTint=10)
    _edit_like_photographer(event, 114, Exposure2012=0.1, Highlights2012=-50)

    result = service.complete(event, automatic_exposure=False)
    assert result["written"] == 16 and result["automatic_exposure"] == "off"
    assert result["from_anchor"] == 14 and result["event_level"] == 2
    moment_photo = _values(event, 101)
    assert moment_photo["Exposure2012"] == "0.5" and moment_photo["Highlights2012"] == "-30"
    assert moment_photo["WhiteBalance"] == '"Custom"' and moment_photo["Temperature"] == "4800"  # same As Shot
    other_moment = _values(event, 113)
    assert other_moment["Exposure2012"] == "0.1" and other_moment["WhiteBalance"] == '"As Shot"'
    lone = _values(event, 117)
    assert lone["Exposure2012"] == "0.3" and lone["Highlights2012"] == "-40"  # anchors' medians
    assert _values(event, 106)["Temperature"] == "4800"  # the anchor itself is the photographer's

    service.undo(event, result["backup"])
    assert _values(event, 101)["Exposure2012"] == "0"


def test_refuses_while_lightroom_is_open(event: Path):
    Path(f"{event}.lock").write_text("")
    with pytest.raises(service.EventEditError):
        service.plan_anchors(event)


def test_undo_only_accepts_this_catalogs_backup(event: Path, tmp_path: Path):
    stranger = tmp_path / "elsewhere.lrcat-backup"
    stranger.write_text("x")
    with pytest.raises(service.EventEditError):
        service.undo(event, stranger)
