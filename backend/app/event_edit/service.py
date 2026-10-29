"""Event flow v1 on a Lightroom Classic catalog (Lightroom closed):

  1. plan_anchors(catalog)  -> cuts the event into moments, puts the anchors in the collection
                               "ProGrapher - Edit these" and gives them a purple label (labels the photographer set
                               are kept). The photographer edits those photos in Lightroom, then closes it.
  2. complete(catalog)      -> reads the edited anchors and writes every other photo (catalog_writer, with backup and
                               a "ProGrapher" History step). Photos the photographer edited are never changed.
  3. undo(catalog, backup)  -> puts the catalog back exactly as it was before step 2 (or step 1).

Reads the catalog read-only for planning; every write goes through catalog_writer's safety (docs/LB_02...).
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.event_edit import brain
from app.event_edit.brain import Photo
from app.lightroom_bridge import catalog_writer as writer


class EventEditError(ValueError):
    """The event cannot be processed; nothing was changed."""


def _catalog(path: str | Path) -> Path:
    catalog = Path(path).expanduser()
    if catalog.suffix.lower() != ".lrcat" or not catalog.is_file():
        raise EventEditError("choose a Lightroom catalog file (.lrcat)")
    if writer.catalog_in_use(catalog):
        raise EventEditError("Lightroom has this catalog open; close Lightroom and try again")
    return catalog


def _seconds(value: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(value)[:19]).timestamp()
    except ValueError:
        return None


def _numbers(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        settings = writer.read_settings(text)
    except ValueError:
        return out
    for key, raw in settings.items():
        if key == "WhiteBalance":
            out[key] = raw.strip('"')
            continue
        try:
            out[key] = float(raw)
        except ValueError:
            continue
    return out


def _as_shot(develop: dict, history_texts: list[str]) -> tuple[float | None, float | None]:
    """The camera's white balance: the current settings while As Shot, else the earliest As Shot History step."""
    for values in [develop] + [_numbers(t) for t in history_texts]:
        if values.get("WhiteBalance") == "As Shot" and "Temperature" in values and "Tint" in values:
            return values["Temperature"], values["Tint"]
    return None, None


def read_event(catalog: Path) -> list[Photo]:
    """Every photo (virtual copies excluded) with its capture time, sliders, As Shot and whether it was edited."""
    db = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
    try:
        rows = db.execute("""SELECT i.id_local, COALESCE(i.originalCaptureTime, i.captureTime), s.text
                             FROM Adobe_images i JOIN Adobe_imageDevelopSettings s ON s.image = i.id_local
                             WHERE i.masterImage IS NULL""").fetchall()
        steps: dict[int, list[tuple[float, str, Any]]] = {}
        for image, created, name, blob in db.execute(
                "SELECT image, dateCreated, name, text FROM Adobe_libraryImageDevelopHistoryStep"):
            steps.setdefault(image, []).append((created or 0.0, name or "", blob))
    except sqlite3.Error as exc:
        raise EventEditError("unsupported catalog layout") from exc
    finally:
        db.close()
    photos = []
    for image, taken, text in rows:
        develop = _numbers(text or "")
        history = sorted(steps.get(image, []), key=lambda s: s[0])
        edited = any(not (name.startswith(writer.AUTOMATIC_STEPS) or name == writer.STEP_NAME) for _, name, _ in history)
        texts = [t for t in (writer._decode_history(blob)[1] for _, _, blob in history) if t]
        kelvin, tint = _as_shot(develop, texts)
        photos.append(Photo(image=image, seconds=_seconds(taken), as_shot_kelvin=kelvin, as_shot_tint=tint,
                            develop=develop, edited_by_photographer=edited))
    return photos


def anchor_ids(catalog: Path) -> list[int]:
    db = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
    try:
        return [r[0] for r in db.execute(
            "SELECT ci.image FROM AgLibraryCollectionImage ci JOIN AgLibraryCollection c ON c.id_local = ci.collection "
            "WHERE c.name = ? AND c.parent IS NULL", (writer.ANCHOR_COLLECTION,))]
    except sqlite3.Error:
        return []
    finally:
        db.close()


def plan_anchors(catalog_path: str | Path, anchor_count: int | None = None) -> dict[str, Any]:
    catalog = _catalog(catalog_path)
    photos = read_event(catalog)
    if not photos:
        raise EventEditError("the catalog has no photos")
    moments = brain.make_moments(photos)
    count = anchor_count or brain.default_anchor_count(len(photos))
    anchors = brain.choose_anchors(moments, count)
    try:
        marked = writer.mark_photos(catalog, [a.image for a in anchors])
    except writer.CatalogWriteError as exc:
        raise EventEditError(str(exc)) from exc
    covered = sum(len(m) for m in moments if any(p.image in set(marked["marked"]) for p in m))
    return {"photos": len(photos), "moments": len(moments), "anchors": len(marked["marked"]),
            "photos_in_anchored_moments": covered, "collection": writer.ANCHOR_COLLECTION,
            "label": writer.ANCHOR_LABEL, "labelled": len(marked["labelled"]), "backup": marked["backup"]}


def _automatic_exposure(catalog: Path, photos: list[Photo], anchors: list[Photo], targets: list[Photo],
                        progress: Callable[[int, int], None] | None) -> tuple[dict[int, float], str]:
    """Target-method exposure for `targets`, calibrated on the edited anchors of this event."""
    from app.event_edit import exposure_target as et
    from app.learning_intake.decoder_vendor import load_decoder_package
    from app.learning_intake.smart_preview_render import find_adobe_color_look

    detector = et.load_face_detector()
    if detector is None:
        return {}, "off: face model not installed"
    previews = catalog.with_name(f"{catalog.stem} Smart Previews.lrdata")
    if not previews.is_dir():
        return {}, "off: no Smart Previews next to the catalog"
    try:
        decoder = load_decoder_package()
    except Exception:  # noqa: BLE001
        return {}, "off: Smart Preview decoder unavailable"
    db = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
    uuid_of = {i: (g or "").upper() for i, g in db.execute("SELECT id_local, id_global FROM Adobe_images")}
    db.close()
    dngs = {p.stem.upper(): p for p in previews.rglob("*.dng")}
    look, curve = find_adobe_color_look(decoder), decoder.load_tone_curve()
    edited = [a for a in anchors if a.edited_by_photographer and "Exposure2012" in a.develop]
    todo = edited + targets
    measured: dict[int, dict] = {}
    for n, photo in enumerate(todo, start=1):
        path = dngs.get(uuid_of.get(photo.image, ""))
        if path is not None:
            try:
                measured[photo.image] = et.measure_face(decoder, decoder.decode_smart_preview(path, long_edge=640),
                                                        look, detector, curve)
            except Exception:  # noqa: BLE001  (one unreadable Smart Preview must not stop the event)
                pass
        if progress:
            progress(n, len(todo))
    style = et.learn_style([{**measured[a.image], "exposure": a.develop["Exposure2012"]}
                            for a in edited if measured.get(a.image)], curve)
    if style is None:
        return {}, "off: fewer than 20 edited anchors with a face"
    autos = et.automatic_exposures({p.image: measured[p.image] for p in targets if p.image in measured}, style, curve)
    return autos, f"on: {len(autos)} photos"


def complete(catalog_path: str | Path, *, automatic_exposure: bool = True,
             progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    catalog = _catalog(catalog_path)
    started = time.perf_counter()
    photos = read_event(catalog)
    ids = set(anchor_ids(catalog))
    if not ids:
        raise EventEditError("choose the photos to edit first (no 'ProGrapher - Edit these' collection)")
    anchors = [p for p in photos if p.image in ids]
    if not any(a.edited_by_photographer for a in anchors):
        raise EventEditError("none of the photos in 'ProGrapher - Edit these' has been edited yet")
    moments = brain.make_moments(photos)
    status = "off"
    autos: dict[int, float] = {}
    if automatic_exposure:
        edited_ids = {a.image for a in anchors if a.edited_by_photographer}
        targets = [p for m in moments if not any(q.image in edited_ids for q in m)
                   for p in m if not p.edited_by_photographer]
        autos, status = _automatic_exposure(catalog, photos, anchors, targets, progress)
    plan = brain.complete_event(moments, anchors, auto_exposure=lambda p: autos.get(p.image))
    try:
        written = writer.write_edits(catalog, plan["edits"])
    except writer.CatalogWriteError as exc:
        raise EventEditError(str(exc)) from exc
    reasons: dict[str, int] = {}
    for item in written["skipped"]:
        reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1
    return {**plan["summary"], "automatic_exposure": status, "written": len(written["written"]),
            "skipped": reasons, "backup": written["backup"], "seconds": round(time.perf_counter() - started, 1)}


def undo(catalog_path: str | Path, backup: str | Path) -> dict[str, Any]:
    catalog = _catalog(catalog_path)
    backup = Path(backup)
    if (backup.suffix != ".lrcat-backup" or backup.parent != catalog.parent / "ProGrapher Backups"
            or not backup.name.startswith(f"{catalog.stem}-")):
        raise EventEditError("not a ProGrapher backup of this catalog")
    try:
        writer.restore_backup(backup, catalog)
    except writer.CatalogWriteError as exc:
        raise EventEditError(str(exc)) from exc
    return {"restored": True}
