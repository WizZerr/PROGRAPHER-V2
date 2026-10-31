"""Event flow v1 on a Lightroom Classic catalog, safe by construction:

  folders(catalog)                  -> the catalog's folders, to choose the EVENT (scope). Nothing works without one.
  plan_anchors / plan_completion / plan_undo
                                    -> DRY RUN in a job: reads the catalog without changing a byte (SQLite immutable
                                       mode), stores the plan and a fingerprint of the event's state, returns what
                                       would change. Nothing is written.
  confirm(job_id)                   -> the only way to change a catalog: re-checks inside the write transaction that
                                       the event is exactly as in the dry run (else "outdated", nothing written), then
                                       writes through catalog_writer (ProGrapher lock, Lightroom closed, backup, one
                                       transaction, photos outside the event refused).
  get_job / cancel                  -> progress and recovery of jobs (app/event_edit/jobs.py).

Undo is selective: only photos still exactly as ProGrapher left them are put back; anything edited since is kept.
Only the latest completion of an event can be undone. Backups are never deleted.
"""
from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from app.event_edit import brain, jobs
from app.event_edit import style as event_style
from app.event_edit.brain import Photo
from app.event_edit.scope import ScopeError, event_id, fingerprint, list_folders, open_readonly, scope_images
from app.lightroom_bridge import catalog_writer as writer

BACKUP_FOLDER = "ProGrapher Backups"
# Confirmation a plan needs, on top of the usual one, when photos get one exposure for the whole event instead of
# one measured on the photo (no Smart Previews, no face model, too few faces, or many photos left unanalysed).
UNIFORM_EXPOSURE = "uniform_exposure"
MAX_UNANALYSED_SHARE = 0.10


class EventEditError(ValueError):
    """The request cannot be carried out; nothing was changed."""


class PlanOutdated(writer.CatalogWriteError):
    """The catalog changed since the dry run."""


def _catalog(path: str | Path) -> Path:
    catalog = Path(path).expanduser()
    if catalog.suffix.lower() != ".lrcat" or not catalog.is_file():
        raise EventEditError("יש לבחור קובץ קטלוג של Lightroom (.lrcat)")
    if writer.catalog_in_use(catalog):
        raise EventEditError("הקטלוג פתוח ב-Lightroom. סגור את Lightroom ונסה שוב.")
    return catalog.resolve()


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


def read_photos(db: sqlite3.Connection, images: set[int]) -> list[Photo]:
    """The event's photos with capture time, sliders, As Shot and whether the photographer edited them."""
    ordered = sorted(images)
    rows, steps = [], {}
    for start in range(0, len(ordered), 500):
        chunk = ordered[start:start + 500]
        marks = ",".join("?" * len(chunk))
        rows += db.execute(f"""SELECT i.id_local, COALESCE(i.originalCaptureTime, i.captureTime), s.text
                               FROM Adobe_images i JOIN Adobe_imageDevelopSettings s ON s.image = i.id_local
                               WHERE i.id_local IN ({marks})""", chunk).fetchall()
        for image, created, name, blob in db.execute(
                f"SELECT image, dateCreated, name, text FROM Adobe_libraryImageDevelopHistoryStep "
                f"WHERE image IN ({marks})", chunk):
            steps.setdefault(image, []).append((created or 0.0, name or "", blob))
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


def folders(catalog_path: str | Path) -> dict[str, Any]:
    catalog = _catalog(catalog_path)
    try:
        return {"catalog": str(catalog), "folders": list_folders(catalog)}
    except ScopeError as exc:
        raise EventEditError("מבנה הקטלוג לא נתמך") from exc


# --- jobs ------------------------------------------------------------------------------------------------------------

def _public(job: dict[str, Any]) -> dict[str, Any]:
    hidden = ("edits", "history_ids", "before", "entries", "expected", "images", "expected_members", "labelled",
              "anchors")
    plan = {k: v for k, v in (job.get("plan") or {}).items() if k not in hidden}
    result = {k: v for k, v in (job.get("result") or {}).items() if k not in ("written_images",)}
    return {"job_id": job["job_id"], "kind": job["kind"], "status": job["status"], "event_id": job["event_id"],
            "progress": {"done": job["progress_done"], "total": job["progress_total"], "phase": job.get("phase")},
            "error": job.get("error"), "plan": plan or None, "result": result or None,
            "parent_job": job.get("parent_job")}


def _start(kind: str, catalog: Path, scope: list[str], work, wait: bool, parent: str | None = None) -> dict:
    job_id = jobs.create(kind, event_id(catalog, scope), catalog, scope, parent)

    def planning() -> None:
        if not jobs.transition(job_id, ("pending",), "planning"):
            return
        try:
            plan, fp = work(job_id)
            jobs.finish_planning(job_id, status="planned", plan=plan, fingerprint=fp)
        except (EventEditError, ScopeError, writer.CatalogWriteError, sqlite3.Error) as exc:
            jobs.finish_planning(job_id, status="failed", error=str(exc), result={"nothing_written": True})
        except Exception as exc:  # noqa: BLE001  (report, never crash the engine)
            jobs.finish_planning(job_id, status="failed", error=f"שגיאה לא צפויה בתכנון: {type(exc).__name__}",
                                 result={"nothing_written": True})
    jobs.run(job_id, planning, wait)
    return get_job(job_id)


def get_job(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)
    if job is None:
        raise EventEditError("הפעולה לא נמצאה")
    if job["status"] in jobs.ACTIVE and not jobs.is_running(job_id):
        _recover(job)
        job = jobs.get(job_id)
    return _public(job)


def cancel(job_id: str) -> dict[str, Any]:
    if not jobs.transition(job_id, ("pending", "planning", "planned"), "cancelled"):
        raise EventEditError("אי אפשר לבטל: הפעולה כבר בכתיבה או הסתיימה")
    return get_job(job_id)


def _recover(job: dict[str, Any]) -> None:
    """A job left active by a crash. Writes are a single transaction: check the catalog for what happened."""
    jid = job["job_id"]
    if job["status"] in ("pending", "planning", "queued"):
        jobs.update(jid, status="interrupted", error="הפעולה נקטעה לפני כתיבה. לא נכתב דבר; אפשר לתכנן מחדש.",
                    result={"nothing_written": True})
        return
    plan, catalog = job["plan"] or {}, jobs.path(job)
    try:
        done, partial = _verify_written(job, plan, catalog)
    except (sqlite3.Error, OSError, KeyError, ValueError):
        jobs.update(jid, status="failed", result={"nothing_written": False},
                    error="לא ניתן לבדוק מה נכתב לפני הקריסה. אל תכתוב שוב; בדוק את הקטלוג מול הגיבוי.")
        return
    if done:
        written = [int(k) for k in plan.get("edits", {})] if job["kind"] == "complete" else []
        jobs.update(jid, status="completed", result={"recovered": True, "written_images": written})
        if job["kind"] == "undo":
            _after_undo(job, plan, recovered=True)
    elif partial:
        jobs.update(jid, status="failed", result={"nothing_written": False},
                    error="מצב לא עקבי אחרי קריסה. אל תכתוב שוב; בדוק את הקטלוג מול הגיבוי.")
    else:
        jobs.update(jid, status="failed", result={"nothing_written": True},
                    error="הפעולה נקטעה. לא נכתב דבר; אפשר לתכנן מחדש.")


def _verify_written(job: dict[str, Any], plan: dict[str, Any], catalog: Path) -> tuple[bool, bool]:
    db = open_readonly(catalog)
    try:
        if job["kind"] == "complete":
            ids = set(plan.get("history_ids", {}).values())
            found = {r[0] for r in db.execute(
                "SELECT id_global FROM Adobe_libraryImageDevelopHistoryStep WHERE name = ?", (writer.STEP_NAME,))} & ids
            return bool(ids) and found == ids, bool(found) and found != ids
        if job["kind"] == "anchors":
            name = plan.get("collection_name") or ""
            rows = db.execute("SELECT id_local, name FROM AgLibraryCollection WHERE name = ? OR name LIKE ?",
                              (name, name + " (%)")).fetchall()
            match = [r for r in rows if sorted(writer.collection_members(db, r[0])) == sorted(plan.get("anchors", []))]
            if match:
                jobs.save_event(plan["event_id"], catalog, job["scope"], collection_id=match[0][0],
                                collection_name=match[0][1], anchors=plan["anchors"])
            return bool(match), False
        if plan.get("kind") == "unmark":
            gone = db.execute("SELECT 1 FROM AgLibraryCollection WHERE id_local = ?", (plan["collection_id"],)).fetchone() is None
            labels = dict(db.execute(f"SELECT id_local, COALESCE(colorLabels, '') FROM Adobe_images WHERE id_local IN "
                                     f"({','.join('?' * len(plan['labelled']))})", plan["labelled"]).fetchall()) \
                if plan["labelled"] else {}
            still = [i for i in plan.get("labels_planned", []) if labels.get(i) == writer.ANCHOR_LABEL]
            collection_ok = gone or not plan["collection_removable"]
            done = collection_ok and not still
            return done, not done and (gone or len(still) < len(plan.get("labels_planned", [])))
        entries = plan.get("entries", [])
        if not entries:
            return True, False
        state = writer.develop_state(db, [e["image"] for e in entries])
        back = [e for e in entries if state.get(e["image"], {}).get("historySettingsID") == e["before"]["historySettingsID"]]
        return len(back) == len(entries), 0 < len(back) < len(entries)
    finally:
        db.close()


def _after_undo(job: dict[str, Any], plan: dict[str, Any], *, recovered: bool = False,
                out: dict[str, Any] | None = None) -> None:
    """Bring the undone job and the event record in line with what the undo did."""
    catalog = jobs.path(job)
    if plan.get("kind") == "unmark":
        removed = out["collection_removed"] if out else plan["collection_removable"]
        kept = out["labels_kept"] if out else sorted(set(plan["labelled"]) - set(plan.get("labels_planned", [])))
        if removed:
            jobs.update(plan["target_job"], status="undone")
            jobs.save_event(plan["event_id"], catalog, job["scope"], collection_id=None, collection_name=None,
                            anchors=[], labelled=kept)
        else:  # the collection stays (the photographer changed it): the marking is still in place
            jobs.save_event(plan["event_id"], catalog, job["scope"], labelled=kept)
        return
    kept_any = bool(out["kept"]) if out else plan.get("kept")
    jobs.update(plan["target_job"], status="partially_undone" if kept_any else "undone")


# --- dry runs ----------------------------------------------------------------------------------------------------

def _column(db: sqlite3.Connection, query: str, ids: list[int]) -> dict:
    """{id: value} for a two-column query over `ids`, in chunks (only the event's photos are read)."""
    out: dict = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        out.update(db.execute(query.format(",".join("?" * len(chunk))), chunk).fetchall())
    return out


def _owned_collection(db: sqlite3.Connection, event: dict | None) -> int | None:
    """The event's ProGrapher collection, only while it exists under the name ProGrapher gave it."""
    if not event or event.get("collection_id") is None:
        return None
    row = db.execute("SELECT name FROM AgLibraryCollection WHERE id_local = ?", (event["collection_id"],)).fetchone()
    return event["collection_id"] if row and row[0] == event.get("collection_name") else None


def plan_anchors(catalog_path: str | Path, folder_keys: list[str], anchor_count: int | None = None,
                 wait: bool = False) -> dict[str, Any]:
    catalog = _catalog(catalog_path)
    if not folder_keys:
        raise EventEditError("יש לבחור את תיקיות האירוע")

    def work(job_id: str):
        eid = event_id(catalog, folder_keys)
        db = open_readonly(catalog)
        try:
            images = scope_images(db, folder_keys)
            if not images:
                raise EventEditError("אין תמונות בתיקיות שנבחרו")
            photos = read_photos(db, images)
            moments = brain.make_moments(photos)
            count = anchor_count or brain.default_anchor_count(len(photos))
            anchors = [a.image for a in brain.choose_anchors(moments, count)]
            event = jobs.get_event(eid)
            owned = _owned_collection(db, event)
            reuse = owned is not None and sorted(writer.collection_members(db, owned)) == sorted(event["anchors"])
            labels = _column(db, "SELECT id_local, COALESCE(colorLabels, '') FROM Adobe_images WHERE id_local IN ({})",
                             anchors)
            fp = fingerprint(db, images, owned)
        finally:
            db.close()
        name = (event or {}).get("collection_name") if reuse else f"{writer.ANCHOR_COLLECTION} [{eid[:6]}]"
        blocking = [] if anchors else [{"reason": "no_anchors"}]
        return ({"event_id": eid, "photos": len(photos), "moments": len(moments), "anchors": anchors,
                 "anchor_count": len(anchors), "to_label": sum(1 for a in anchors if not labels.get(a)),
                 "label": writer.ANCHOR_LABEL, "collection_name": name, "reuse_collection": reuse,
                 "owned_collection": owned if reuse else None, "fp_collection": owned, "images": sorted(images),
                 "backup_folder": str(catalog.parent / BACKUP_FOLDER), "blocking": blocking}, fp)
    return _start("anchors", catalog, folder_keys, work, wait)


def _changed_only(text: str, values: dict, is_raw: bool) -> dict:
    """Keep only the sliders whose value differs from the photo's current one (Temperature/Tint stay together)."""
    try:
        current = writer.read_settings(text)
        wanted = writer.normalize_edit(values, is_raw=is_raw)
    except ValueError:
        return dict(values)
    differs = {k for k, v in wanted.items() if current.get(k) != writer._lua(v)}
    if differs & {"Temperature", "Tint", "WhiteBalance", "CustomTemperature", "CustomTint"}:
        differs |= {"Temperature", "Tint"}
    return {k: v for k, v in values.items() if k in differs}


def plan_completion(catalog_path: str | Path, folder_keys: list[str], *, fill_unanchored: bool = False,
                    automatic_exposure: bool = False, wait: bool = False) -> dict[str, Any]:
    catalog = _catalog(catalog_path)
    if not folder_keys:
        raise EventEditError("יש לבחור את תיקיות האירוע")

    def work(job_id: str):
        eid = event_id(catalog, folder_keys)
        event = jobs.get_event(eid)
        db = open_readonly(catalog)
        try:
            images = scope_images(db, folder_keys)
            owned = _owned_collection(db, event)
            if owned is None:
                raise EventEditError("קודם צריך לבחור תמונות לעריכה לאירוע הזה")
            # the anchors ProGrapher recorded (not whatever the collection holds now): removing photos from the
            # collection must not lower the bar of the evidence gate
            anchor_ids = set(event.get("anchors", [])) & images
            photos = read_photos(db, images)
            moments = brain.make_moments(photos)
            anchors = [p for p in photos if p.image in anchor_ids]
            assessment = brain.assess_anchors(moments, anchors)
            autos: dict[int, float] = {}
            auto_status = {"state": "off", "reason": "disabled"}
            if fill_unanchored and automatic_exposure:
                autos, auto_status = _automatic_exposure(catalog, db, anchors, moments, job_id)
            result = brain.complete_event(moments, anchors, auto_exposure=lambda p: autos.get(p.image),
                                          fill_unanchored=fill_unanchored)
            wanted = list(result["edits"])
            texts = _column(db, "SELECT image, COALESCE(text, '') FROM Adobe_imageDevelopSettings WHERE image IN ({})",
                            wanted)
            raw_ext = {i: (e or "").lower() not in writer.NON_RAW for i, e in _column(
                db, "SELECT i.id_local, f.extension FROM Adobe_images i JOIN AgLibraryFile f ON f.id_local = i.rootFile "
                    "WHERE i.id_local IN ({})", wanted).items()}
            edits, skipped = {}, dict(result["skipped"])
            for image, values in result["edits"].items():
                changed = _changed_only(texts.get(image, ""), values, raw_ext.get(image, True))
                if changed:
                    edits[image] = changed
                else:
                    skipped[image] = "already_up_to_date"
            before = writer.develop_state(db, list(edits))
            expected = {image: {k: writer._lua(v) for k, v in
                                writer.normalize_edit(values, is_raw=raw_ext.get(image, True)).items()}
                        for image, values in edits.items()}
            fp = fingerprint(db, images, owned)
        finally:
            db.close()
        reasons: dict[str, int] = {}
        for reason in skipped.values():
            reasons[reason] = reasons.get(reason, 0) + 1
        warnings = []
        if assessment["light_bins_without_example"]:
            warnings.append({"reason": "light_without_example", "bins": assessment["light_bins_without_example"]})
        if assessment["covered_share"] < 0.5:
            warnings.append({"reason": "low_coverage", "covered_share": assessment["covered_share"]})
        sliders = sorted({k for v in edits.values() for k in v})
        return ({"event_id": eid, "assessment": assessment, "will_write": len(edits), "skipped": reasons,
                 "skipped_edited": result["summary"]["skipped_edited"], "from_anchor": result["summary"]["from_anchor"],
                 "automatic": result["summary"]["automatic"], "event_level": result["summary"]["event_level"],
                 "sliders": sliders, "warnings": warnings, "blocking": assessment["blocking"],
                 "automatic_exposure": auto_status, "fill_unanchored": fill_unanchored,
                 "backup_folder": str(catalog.parent / BACKUP_FOLDER), "fp_collection": owned,
                 "images": sorted(images), "edits": {str(k): v for k, v in edits.items()},
                 "history_ids": {str(k): str(uuid.uuid4()).upper() for k in edits},
                 "before": {str(k): v for k, v in before.items()},
                 "expected": {str(k): v for k, v in expected.items()}}, fp)
    return _start("complete", catalog, folder_keys, work, wait)


def plan_automatic(catalog_path: str | Path, folder_keys: list[str], profile_id: str, *, relearn: bool = False,
                   wait: bool = False) -> dict[str, Any]:
    """Dry run of editing the whole event automatically from a learning profile's style (as Imagen does): base
    sliders from the profile, exposure by the face "target" method (or the profile's level), white balance As Shot.
    Photos the photographer already edited are left alone. Nothing is written."""
    from app.learning_intake.service import LearningIntakeError, LearningProfileStore

    catalog = _catalog(catalog_path)
    if not folder_keys:
        raise EventEditError("יש לבחור את תיקיות האירוע")
    store = LearningProfileStore()
    try:
        store.get(profile_id)
    except LearningIntakeError as exc:
        raise EventEditError("פרופיל הלמידה לא נמצא") from exc

    def work(job_id: str):
        eid = event_id(catalog, folder_keys)
        style = None if relearn else store.get_style(profile_id)
        if style is None or style.get("version") != event_style.STYLE_VERSION:  # learnt by an older rule: again
            jobs.update(job_id, phase="learning", progress_done=0, progress_total=0)
            try:
                style = store.learn_style(profile_id, progress=lambda d, t: jobs.update(
                    job_id, progress_done=d, progress_total=t))
            except LearningIntakeError as exc:
                raise EventEditError("אין בפרופיל תמונות ערוכות בצבע עם Smart Previews ללמוד מהן") from exc
        db = open_readonly(catalog)
        try:
            images = scope_images(db, folder_keys)
            if not images:
                raise EventEditError("אין תמונות בתיקיות שנבחרו")
            photos = read_photos(db, images)
            targets = [p for p in photos if not p.edited_by_photographer]
            exposures, exposure, paths = _event_exposures(catalog, db, targets, style, job_id)
            flash = _event_flash(db, [p.image for p in targets])
            _apply_flash_offsets(exposures, exposure, flash, style)
            balance, white_balance = _event_white_balance(catalog, db, targets, style, flash, paths, job_id)
            edits_all = {}
            for photo in targets:
                values = {k: v for k, v in style["base"].items()}
                values["Exposure2012"] = round(min(max(exposures[photo.image], -5.0), 5.0), 2)
                values.update(balance.get(photo.image, {}))
                edits_all[photo.image] = values
            ids = list(edits_all)
            texts = _column(db, "SELECT image, COALESCE(text, '') FROM Adobe_imageDevelopSettings WHERE image IN ({})", ids)
            raw_ext = {i: (e or "").lower() not in writer.NON_RAW for i, e in _column(
                db, "SELECT i.id_local, f.extension FROM Adobe_images i JOIN AgLibraryFile f ON f.id_local = i.rootFile "
                    "WHERE i.id_local IN ({})", ids).items()}
            edits, skipped = {}, {p.image: "edited_by_photographer" for p in photos if p.edited_by_photographer}
            for image, values in edits_all.items():
                changed = _changed_only(texts.get(image, ""), values, raw_ext.get(image, True))
                if changed:
                    edits[image] = changed
                else:
                    skipped[image] = "already_up_to_date"
            before = writer.develop_state(db, list(edits))
            expected = {image: {k: writer._lua(v) for k, v in
                                writer.normalize_edit(values, is_raw=raw_ext.get(image, True)).items()}
                        for image, values in edits.items()}
            fp = fingerprint(db, images)
        finally:
            db.close()
        reasons: dict[str, int] = {}
        for reason in skipped.values():
            reasons[reason] = reasons.get(reason, 0) + 1
        warnings, acknowledgements = _exposure_acknowledgements(exposure)
        return ({"event_id": eid, "mode": "automatic", "profile_id": profile_id, "photos": len(photos),
                 "will_write": len(edits), "skipped": reasons, "sliders": sorted({k for v in edits.values() for k in v}),
                 "exposure": exposure, "white_balance": "as_shot", "white_balance_rules": white_balance,
                 "style": {"photos": style.get("photos"), "faces": style.get("faces"),
                           "black_and_white_excluded": style.get("black_and_white_excluded", 0),
                           "learned_at": style.get("learned_at"), "base": style.get("base")},
                 "warnings": warnings, "blocking": [] if edits else [{"reason": "nothing_to_write"}],
                 "requires_acknowledgement": acknowledgements if edits else [],
                 "backup_folder": str(catalog.parent / BACKUP_FOLDER), "fp_collection": None,
                 "images": sorted(images), "edits": {str(k): v for k, v in edits.items()},
                 "history_ids": {str(k): str(uuid.uuid4()).upper() for k in edits},
                 "before": {str(k): v for k, v in before.items()},
                 "expected": {str(k): v for k, v in expected.items()}}, fp)
    return _start("complete", catalog, folder_keys, work, wait)


def _event_exposures(catalog: Path, db: sqlite3.Connection, targets: list[Photo], style: dict, job_id: str
                     ) -> tuple[dict[int, float], dict[str, Any], dict[int, Path] | None]:
    """Exposure for every target photo: the face "target" method on this event's Smart Previews when possible,
    otherwise the profile's typical level. `analysed` counts the photos whose own Smart Preview was measured; every
    other photo gets one uniform value (see UNIFORM_EXPOSURE). Also returns the matched Smart Previews, if it
    looked for them."""
    from app.event_edit import exposure_target as et

    level = float(style.get("exposure_level") or 0.0)
    fallback = {p.image: level for p in targets}
    paths: dict[int, Path] | None = None

    def uniform(reason: str, **extra) -> tuple[dict[int, float], dict[str, Any], dict[int, Path] | None]:
        return fallback, {"mode": "profile_level", "reason": reason, "level": level, "photos": len(targets),
                          "analysed": 0, **extra}, paths
    if not style.get("exposure_style"):
        return uniform("profile_has_no_face_style")
    previews = catalog.with_name(f"{catalog.stem} Smart Previews.lrdata")
    if not previews.is_dir():
        return uniform("no_smart_previews")
    measure, curve, reason = et.face_measurer(long_edge=480)
    if measure is None:
        return uniform(reason)
    paths, matching = _match_smart_previews(db, previews, [p.image for p in targets], job_id)
    if not paths:
        return uniform("smart_previews_not_matched", matching=matching)
    jobs.update(job_id, phase="measuring", progress_done=0, progress_total=len(targets))
    measured: dict[int, dict] = {}
    for n, photo in enumerate(targets, start=1):
        path = paths.get(photo.image)
        if path is not None:
            m = measure(path)
            if m is not None:
                measured[photo.image] = m
        if n % 25 == 0 or n == len(targets):
            jobs.update(job_id, progress_done=n)
    exposure_style = et.ExposureStyle(**style["exposure_style"])
    solved = et.solve_level(list(measured.values()), exposure_style, curve)
    if solved is None:
        return uniform("too_few_faces_in_event", measured=len(measured), matched=len(paths), matching=matching)
    autos = et.automatic_exposures(measured, exposure_style, curve)
    event_level = solved[0]
    faces = sum(1 for m in measured.values() if m.get("face_rgb") is not None)
    return ({p.image: autos.get(p.image, event_level) for p in targets},
            {"mode": "faces", "level": round(event_level, 2), "faces": faces, "measured": len(measured),
             "matched": len(paths), "matching": matching, "photos": len(targets), "analysed": len(measured)}, paths)


def _event_flash(db: sqlite3.Connection, images: list[int]) -> dict[int, bool]:
    """Whether the flash fired, per photo, from the EXIF Lightroom harvested (absent: unknown)."""
    columns = {r[1] for r in db.execute("PRAGMA table_info(AgHarvestedExifMetadata)")}
    if not {"image", "flashFired"} <= columns:
        return {}
    return {image: bool(value) for image, value in _column(
        db, "SELECT image, flashFired FROM AgHarvestedExifMetadata WHERE flashFired IS NOT NULL AND image IN ({})",
        images).items()}


def _apply_flash_offsets(exposures: dict[int, float], exposure: dict[str, Any], flash: dict[int, bool],
                         style: dict) -> None:
    """The editor's correction on top of the face method, for photos with and without flash (faces mode only: the
    corrections were learnt against the face method)."""
    offsets = style.get("exposure_flash_offsets") or {}
    if exposure["mode"] != "faces" or not offsets:
        return
    corrected = 0
    for image in exposures:
        key = event_style.flash_key(flash.get(image))
        if key in offsets:
            exposures[image] += offsets[key]
            corrected += 1
    exposure.update(flash_offsets=offsets, flash_corrected=corrected)


def _event_white_balance(catalog: Path, db: sqlite3.Connection, targets: list[Photo], style: dict,
                         flash: dict[int, bool], paths: dict[int, Path] | None, job_id: str
                         ) -> tuple[dict[int, dict[str, float]], dict[str, Any]]:
    """Temperature/Tint for photos in a kind of light where the editor nearly always moved the camera's As Shot; every
    other photo keeps As Shot. Needs the photo's Smart Preview (the camera's As Shot) and whether the flash fired."""
    from app.learning_intake.white_balance import as_shot_temperature_tint, read_wb_tags

    rules = style.get("white_balance_rules") or []
    info: dict[str, Any] = {"rules": rules, "photos": 0}
    if not rules:
        return {}, info
    if paths is None:
        previews = catalog.with_name(f"{catalog.stem} Smart Previews.lrdata")
        paths = _match_smart_previews(db, previews, [p.image for p in targets], job_id)[0] if previews.is_dir() else {}
    out: dict[int, dict[str, float]] = {}
    for photo in targets:
        key, path = event_style.flash_key(flash.get(photo.image)), paths.get(photo.image)
        if key is None or path is None:
            continue
        try:
            kelvin, tint = as_shot_temperature_tint(read_wb_tags(path))
        except Exception:  # noqa: BLE001, S112  (unreadable white-balance tags: the photo keeps As Shot)
            continue
        light = event_style.kelvin_bin(kelvin)
        rule = next((r for r in rules if light == (r["kelvin_min"], r["kelvin_max"]) and r["flash"] == key), None)
        if rule is None:
            continue
        out[photo.image] = {"Temperature": round(min(max(1e6 / (1e6 / kelvin + rule["mired"]), 2000), 50000)),
                            "Tint": round(min(max(tint, -150), 150))}
    info["photos"] = len(out)
    return out, info


def _exposure_acknowledgements(exposure: dict[str, Any]) -> tuple[list[dict], list[str]]:
    """Warnings, and the dedicated confirmations a plan needs, when photos get a uniform exposure instead of one
    measured on the photo: one value for the whole event is wrong wherever the light changes."""
    warnings: list[dict] = []
    total = exposure.get("photos") or 0
    unanalysed = total - (exposure.get("analysed") or 0)
    if exposure["mode"] != "faces":
        warnings.append({"reason": "exposure_from_profile_level", "detail": exposure.get("reason"),
                         "photos": total})
        return warnings, ([UNIFORM_EXPOSURE] if total else [])
    if unanalysed:
        warnings.append({"reason": "photos_without_analysis", "photos": unanalysed, "of": total})
    return warnings, ([UNIFORM_EXPOSURE] if total and unanalysed / total > MAX_UNANALYSED_SHARE else [])


def _match_smart_previews(db: sqlite3.Connection, previews: Path, images: list[int], job_id: str
                          ) -> tuple[dict[int, Path], dict[str, int]]:
    """Smart Preview of each photo: by the photo's or file's catalog UUID (the DNG's name), else - e.g. in a catalog
    made with "Export as Catalog" - by the RAW file name stored inside each Smart Preview (DNG tag 50827).

    Every photo the UUIDs leave unmatched is looked up by name. A name is used only when it is unambiguous: exactly
    one file in the whole catalog has it (two cameras both write IMG_0001.CR3) and exactly one Smart Preview not
    already owned by another photo carries it. Anything else stays unmatched: never guess."""
    from app.learning_intake.dng_diagnostics import read_original_raw_file_name

    dngs = {p.stem.upper(): p for p in previews.rglob("*.dng")}
    ids = _column(db, "SELECT i.id_local, i.id_global FROM Adobe_images i WHERE i.id_local IN ({})", images)
    file_cols = {r[1] for r in db.execute("PRAGMA table_info(AgLibraryFile)")}
    file_ids = _column(db, "SELECT i.id_local, f.id_global FROM Adobe_images i JOIN AgLibraryFile f "
                           "ON f.id_local = i.rootFile WHERE i.id_local IN ({})", images) if "id_global" in file_cols else {}
    paths = {}
    for image in images:
        path = dngs.get((ids.get(image) or "").upper()) or dngs.get((file_ids.get(image) or "").upper())
        if path is not None:
            paths[image] = path
    stats = {"by_id": len(paths), "by_name": 0, "ambiguous": 0, "unmatched": 0}
    missing = [image for image in images if image not in paths]
    if not missing:
        return paths, stats
    # Smart Previews named after any photo or file of the catalog belong to that photo, even outside the event.
    owned = {(r[0] or "").upper() for r in db.execute("SELECT id_global FROM Adobe_images")}
    if "id_global" in file_cols:
        owned |= {(r[0] or "").upper() for r in db.execute("SELECT id_global FROM AgLibraryFile")}
    free = [p for stem, p in dngs.items() if stem not in owned]
    files_per_name: dict[str, int] = {}
    for (name,) in db.execute("SELECT UPPER(baseName || '.' || COALESCE(extension, '')) FROM AgLibraryFile"):
        files_per_name[name] = files_per_name.get(name, 0) + 1
    names = _column(db, "SELECT i.id_local, UPPER(f.baseName || '.' || COALESCE(f.extension, '')) FROM Adobe_images i "
                        "JOIN AgLibraryFile f ON f.id_local = i.rootFile WHERE i.id_local IN ({})", missing)
    jobs.update(job_id, phase="matching", progress_done=0, progress_total=len(free))
    by_name: dict[str, Path | None] = {}
    for n, path in enumerate(free, start=1):
        name = (read_original_raw_file_name(path) or "").upper()
        if name:
            by_name[name] = None if name in by_name else path  # the same name in two Smart Previews: never guess
        if n % 200 == 0 or n == len(free):
            jobs.update(job_id, progress_done=n)
    for image in missing:
        name = names.get(image) or ""
        if files_per_name.get(name, 0) > 1 or (name in by_name and by_name[name] is None):
            stats["ambiguous"] += 1
        elif by_name.get(name) is not None:
            paths[image] = by_name[name]
            stats["by_name"] += 1
        else:
            stats["unmatched"] += 1
    return paths, stats


def _undo_entries(job: dict[str, Any]) -> list[dict[str, Any]]:
    """What a completion wrote, per photo: the History step id, the values as stored, the state before."""
    plan = job["plan"] or {}
    written = set((job.get("result") or {}).get("written_images", []))
    return [{"image": int(k), "history_id": plan["history_ids"][k], "values": plan["expected"][k],
             "before": plan["before"][k]}
            for k in plan.get("edits", {}) if int(k) in written and k in plan.get("before", {})]


def _plan_unmark(target: dict[str, Any], wait: bool) -> dict[str, Any]:
    """Undo of choosing anchors: only the latest marking of the event, and only before any completion used it."""
    later = [j for j in jobs.jobs_for_event(target["event_id"], "anchors") + jobs.jobs_for_event(target["event_id"], "complete")
             if j["created"] > target["created"] and j["status"] in ("completed", "queued", "writing", "partially_undone")]
    if later:
        raise EventEditError("אחרי בחירת התמונות הזו כבר בוצעה פעולה נוספת באירוע; אפשר לבטל רק את הפעולה האחרונה.")
    catalog = _catalog(target["catalog"])
    event = jobs.get_event(target["event_id"]) or {}
    if event.get("collection_id") is None:
        raise EventEditError("לא נמצא ה-Collection של האירוע")

    def work(_job_id: str):
        db = open_readonly(catalog)
        try:
            members = sorted(writer.collection_members(db, event["collection_id"]))
            images = set(event.get("anchors", [])) | set(event.get("labelled", []))
            labels = _column(db, "SELECT id_local, COALESCE(colorLabels, '') FROM Adobe_images WHERE id_local IN ({})",
                             sorted(images))
            fp = fingerprint(db, images, event["collection_id"])
        finally:
            db.close()
        intact = members == sorted(event.get("anchors", []))
        ours = [i for i in event.get("labelled", []) if labels.get(i) == writer.ANCHOR_LABEL]
        return ({"event_id": target["event_id"], "target_job": target["job_id"], "kind": "unmark",
                 "collection_name": event.get("collection_name"), "collection_id": event["collection_id"],
                 "collection_removable": intact, "expected_members": event.get("anchors", []),
                 "labels_to_clear": len(ours), "labelled": event.get("labelled", []), "labels_planned": ours,
                 "images": sorted(images), "fp_collection": event["collection_id"],
                 "backup_folder": str(catalog.parent / BACKUP_FOLDER), "blocking": []}, fp)
    return _start("undo", catalog, target["scope"], work, wait, parent=target["job_id"])


def plan_undo(job_id: str, wait: bool = False) -> dict[str, Any]:
    target = jobs.get(job_id)
    if target is not None and target["kind"] == "anchors" and target["status"] == "completed":
        return _plan_unmark(target, wait)
    if target is None or target["kind"] != "complete":
        raise EventEditError("אפשר לבטל רק השלמת אירוע או בחירת תמונות")
    if target["status"] != "completed":
        raise EventEditError("ההשלמה הזו לא במצב שאפשר לבטל (כבר בוטלה, נכשלה או לא הסתיימה)")
    later = [j for j in jobs.jobs_for_event(target["event_id"], "complete")
             if j["created"] > target["created"] and j["status"] in ("completed", "queued", "writing", "partially_undone")]
    if later:
        raise EventEditError("יש השלמה מאוחרת יותר לאירוע הזה. אפשר לבטל רק את ההשלמה האחרונה.")
    catalog = _catalog(target["catalog"])
    entries = _undo_entries(target)

    def work(_job_id: str):
        db = open_readonly(catalog)
        try:
            state = writer.develop_state(db, [e["image"] for e in entries])
            revertible, kept = [], {}
            for e in entries:
                now = state.get(e["image"])
                same = (now is not None and now["historySettingsID"] == e["history_id"]
                        and now.get("last_step") == e["history_id"])
                if same:
                    try:
                        current = writer.read_settings(now["text"])
                    except ValueError:
                        current = {}
                    same = all(current.get(k) == v for k, v in e["values"].items())
                if same:
                    revertible.append(e)
                else:
                    kept["changed_after_prographer"] = kept.get("changed_after_prographer", 0) + 1
            fp = fingerprint(db, {e["image"] for e in entries})
        finally:
            db.close()
        return ({"event_id": target["event_id"], "target_job": job_id, "will_revert": len(revertible),
                 "kept": kept, "entries": revertible, "images": sorted(e["image"] for e in entries),
                 "backup_folder": str(catalog.parent / BACKUP_FOLDER), "blocking": []}, fp)
    return _start("undo", catalog, target["scope"], work, wait, parent=job_id)


# --- executing a confirmed plan ------------------------------------------------------------------------------------

def confirm(job_id: str, wait: bool = False, acknowledged: Iterable[str] = ()) -> dict[str, Any]:
    job = jobs.get(job_id)
    if job is None:
        raise EventEditError("הפעולה לא נמצאה")
    if job["status"] != "planned":
        raise EventEditError("אפשר לאשר רק תוכנית שהוכנה ועוד לא בוצעה")
    plan = job["plan"] or {}
    if plan.get("blocking"):
        raise EventEditError("התוכנית חסומה: " + ", ".join(b["reason"] for b in plan["blocking"]))
    if set(plan.get("requires_acknowledgement") or []) - set(acknowledged):
        raise EventEditError("בתוכנית הזו תמונות יקבלו חשיפה אחידה שלא נמדדה עליהן. "
                             "יש לאשר במפורש את החשיפה האחידה לפני הכתיבה. לא נכתב דבר.")
    catalog = _catalog(job["catalog"])
    busy = [j for j in jobs.jobs_for_catalog(catalog, ("queued", "writing")) if j["job_id"] != job_id]
    if busy:
        raise EventEditError("כבר מתבצעת כתיבה לקטלוג הזה")
    if not jobs.transition(job_id, ("planned",), "queued"):
        raise EventEditError("התוכנית כבר אושרה")
    images = set(plan.get("images", []))
    collection = plan.get("fp_collection")

    def check(db: sqlite3.Connection) -> None:
        if fingerprint(db, images, collection) != job["fingerprint"]:
            raise PlanOutdated("האירוע השתנה מאז הבדיקה. לא נכתב דבר; יש להכין תוכנית חדשה.")

    def execute() -> None:
        if not jobs.transition(job_id, ("queued",), "writing"):
            return
        stage = {"committed": False}
        try:
            result = _execute(job, catalog, images, check, stage)
            jobs.update(job_id, status="completed", result=result)
        except PlanOutdated as exc:
            jobs.update(job_id, status="outdated", error=str(exc), result={"nothing_written": True})
        except writer.CatalogWriteError as exc:  # raised by the writer before COMMIT, or after restoring the backup
            jobs.update(job_id, status="failed", error=_hebrew(str(exc)), result={"nothing_written": True})
        except Exception as exc:  # noqa: BLE001
            if stage["committed"]:
                jobs.update(job_id, status="failed", result={"nothing_written": False},
                            error=f"הכתיבה לקטלוג הסתיימה אבל שמירת המצב נכשלה ({type(exc).__name__}). "
                                  "אל תכתוב שוב; בדוק את הקטלוג.")
            else:  # the writer rolled back: its session never commits after an exception
                jobs.update(job_id, status="failed", result={"nothing_written": True},
                            error=f"שגיאה לא צפויה בכתיבה ({type(exc).__name__}). לא נכתב דבר.")
    jobs.run(job_id, execute, wait)
    return get_job(job_id)


def _hebrew(message: str) -> str:
    if "already writing" in message:
        return "כבר מתבצעת כתיבה לקטלוג הזה. לא נכתב דבר."
    if "Lightroom" in message and ("open" in message or "opened" in message):
        return "Lightroom פתח את הקטלוג. לא נכתב דבר; סגור את Lightroom ונסה שוב."
    if "in use" in message:
        return "הקטלוג תפוס על ידי תוכנה אחרת. לא נכתב דבר."
    if "History-step format" in message:
        return "גרסת הקטלוג לא מוכרת ל-ProGrapher (פורמט ההיסטוריה). לא נכתב דבר."
    return message


def _execute(job: dict[str, Any], catalog: Path, images: set[int], check, stage: dict[str, bool]) -> dict[str, Any]:
    plan, kind = job["plan"], job["kind"]
    if kind == "anchors":
        event = jobs.get_event(plan["event_id"]) or {}
        out = writer.mark_photos(catalog, plan["anchors"], collection_name=plan["collection_name"],
                                 owned_collection=plan.get("owned_collection"),
                                 expected_members=event.get("anchors") if plan.get("reuse_collection") else None,
                                 allowed_images=images, check=check)
        stage["committed"] = out["backup"] is not None
        if out["collection"] is None:
            raise PlanOutdated("התמונות שתוכננו לסימון כבר לא בקטלוג. לא נכתב דבר; יש להכין תוכנית חדשה.")
        labelled = sorted(set(event.get("labelled", [])) | set(out["labelled"]))
        jobs.save_event(plan["event_id"], catalog, job["scope"], collection_id=out["collection"],
                        collection_name=out["collection_name"], anchors=out["marked"], labelled=labelled)
        return {"backup": out["backup"], "marked": len(out["marked"]), "labelled": len(out["labelled"]),
                "collection_name": out["collection_name"], "created_collection": out["created"]}
    if kind == "complete":
        edits = {int(k): v for k, v in plan["edits"].items()}
        history = {int(k): v for k, v in plan["history_ids"].items()}
        jobs.update(job["job_id"], progress_total=len(edits))
        out = writer.write_edits(catalog, edits, allowed_images=images, history_ids=history, check=check)
        stage["committed"] = out["backup"] is not None
        reasons: dict[str, int] = {}
        for s in out["skipped"]:
            reasons[s["reason"]] = reasons.get(s["reason"], 0) + 1
        jobs.update(job["job_id"], progress_done=len(out["written"]))
        return {"backup": out["backup"], "written": len(out["written"]), "skipped_at_write": reasons,
                "written_images": [w["image"] for w in out["written"]], "seconds": round(out["seconds"], 1)}
    if plan.get("kind") == "unmark":
        out = writer.unmark_photos(catalog, plan["collection_id"], collection_name=plan["collection_name"],
                                   expected_members=plan["expected_members"], labelled=plan["labelled"], check=check)
        stage["committed"] = True
        _after_undo(job, plan, out=out)
        return {"backup": out["backup"], "collection_removed": out["collection_removed"],
                "labels_cleared": len(out["labels_cleared"]), "labels_kept": len(out["labels_kept"])}
    out = writer.revert_edits(catalog, plan["entries"], check=check)
    stage["committed"] = True
    _after_undo(job, plan, out=out)
    return {"backup": out["backup"], "reverted": len(out["reverted"]), "kept": len(out["kept"])}


# --- automatic exposure (opt-in, only for moments without an edited anchor) -----------------------------------------

def _automatic_exposure(catalog: Path, db: sqlite3.Connection, anchors: list[Photo], moments: list[list[Photo]],
                        job_id: str) -> tuple[dict[int, float], dict[str, Any]]:
    from app.event_edit import exposure_target as et
    from app.learning_intake.decoder_vendor import load_decoder_package
    from app.learning_intake.smart_preview_render import find_adobe_color_look

    detector = et.load_face_detector()
    if detector is None:
        return {}, {"state": "off", "reason": "face_model_missing"}
    previews = catalog.with_name(f"{catalog.stem} Smart Previews.lrdata")
    if not previews.is_dir():
        return {}, {"state": "off", "reason": "no_smart_previews"}
    try:
        decoder = load_decoder_package()
    except Exception:  # noqa: BLE001
        return {}, {"state": "off", "reason": "decoder_unavailable"}
    edited = [a for a in anchors if a.edited_by_photographer and "Exposure2012" in a.develop]
    edited_ids = {a.image for a in edited}
    targets = [p for m in moments if not any(q.image in edited_ids for q in m) for p in m if not p.edited_by_photographer]
    todo = edited + targets
    uuid_of = {i: (g or "").upper() for i, g in _column(
        db, "SELECT id_local, id_global FROM Adobe_images WHERE id_local IN ({})", [p.image for p in todo]).items()}
    dngs = {p.stem.upper(): p for p in previews.rglob("*.dng")}
    look, curve = find_adobe_color_look(decoder), decoder.load_tone_curve()
    jobs.update(job_id, progress_total=len(todo))
    measured: dict[int, dict] = {}
    for n, photo in enumerate(todo, start=1):
        path = dngs.get(uuid_of.get(photo.image, ""))
        if path is not None:
            try:
                measured[photo.image] = et.measure_face(decoder, decoder.decode_smart_preview(path, long_edge=640),
                                                        look, detector, curve)
            except Exception:  # noqa: BLE001  (one unreadable Smart Preview must not stop the event)
                pass
        if n % 25 == 0:
            jobs.update(job_id, progress_done=n)
    style = et.learn_style([{**measured[a.image], "exposure": a.develop["Exposure2012"]}
                            for a in edited if measured.get(a.image)], curve)
    if style is None:
        return {}, {"state": "off", "reason": "too_few_anchor_faces"}
    autos = et.automatic_exposures({p.image: measured[p.image] for p in targets if p.image in measured}, style, curve)
    return autos, {"state": "on", "reason": None, "photos": len(autos)}


def event_status(catalog_path: str | Path, folder_keys: list[str]) -> dict[str, Any]:
    """Where an event stands, so the screen can resume: its anchors and its latest completion."""
    catalog = Path(catalog_path).expanduser().resolve()
    eid = event_id(catalog, folder_keys)
    event = jobs.get_event(eid) or {}
    completions = [j for j in jobs.jobs_for_event(eid, "complete") if j["status"] in ("completed", "partially_undone",
                                                                                    "undone")]
    return {"event_id": eid, "collection_name": event.get("collection_name"),
            "anchors": len(event.get("anchors", [])),
            "latest_completion": _public(completions[-1]) if completions else None}
