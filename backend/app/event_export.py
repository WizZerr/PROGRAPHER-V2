from __future__ import annotations

import collections
import hashlib
import json
import re
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from xml.sax.saxutils import escape, quoteattr

from .recipes import canonicalize_recipe


EXPORT_FORMAT = "prographer-lightroom-xmp-export-v1"
CRS_NS = "http://ns.adobe.com/camera-raw-settings/1.0/"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
X_NS = "adobe:ns:meta/"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_export_schema(conn: sqlite3.Connection) -> None:
    """
    Additive / idempotent Stage 7 migration.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS event_exports (
            id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            export_format TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ready',
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            photo_count INTEGER NOT NULL DEFAULT 0,
            approved_count INTEGER NOT NULL DEFAULT 0,
            corrected_count INTEGER NOT NULL DEFAULT 0,
            profile_versions_json TEXT NOT NULL DEFAULT '[]',
            decision_fingerprint TEXT NOT NULL,
            manifest_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_event_exports_event
            ON event_exports(event_id, created_at DESC);
        """
    )


def _safe_json(value: Any, fallback):
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return fallback


def _slug(value: str, fallback: str = "event") -> str:
    text = str(value or "").strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", text)
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return text[:90] or fallback


def _latest_current_decisions_by_photo(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    user_id: str,
) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT s.*
        FROM ai_learning_samples s
        WHERE s.user_id=? AND s.source_event_id=? AND s.is_current=1
        ORDER BY s.created_at DESC
        """,
        (user_id, event_id),
    ).fetchall()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        photo_id = item.get("source_photo_id")
        if not photo_id or photo_id in result:
            continue
        item["ai_recipe"] = _safe_json(item.get("ai_recipe_json"), {})
        item["photographer_recipe"] = _safe_json(
            item.get("photographer_recipe_json"),
            {},
        )
        item["delta"] = _safe_json(item.get("delta_json"), {})
        result[photo_id] = item
    return result


def _latest_predictions_by_photo(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    user_id: str,
) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.*
        FROM photo_ai_predictions p
        INNER JOIN events e ON e.id=p.event_id
        WHERE p.event_id=? AND p.user_id=? AND e.user_id=?
        ORDER BY p.created_at DESC
        """,
        (event_id, user_id, user_id),
    ).fetchall()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        photo_id = item["photo_id"]
        if photo_id in result:
            continue
        item["recipe"] = _safe_json(item.pop("recipe_json", "{}"), {})
        item["provenance"] = _safe_json(item.pop("provenance_json", "{}"), {})
        result[photo_id] = item
    return result


def _decision_fingerprint(decisions: dict[str, dict[str, Any]]) -> str:
    payload = [
        {
            "photo_id": photo_id,
            "sample_id": item["id"],
            "updated_at": item.get("updated_at"),
        }
        for photo_id, item in sorted(decisions.items())
    ]
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _export_public(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["profile_versions"] = _safe_json(
        item.pop("profile_versions_json", "[]"),
        [],
    )
    item["manifest"] = _safe_json(item.pop("manifest_json", "{}"), {})
    return item


def latest_event_export(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    user_id: str,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT *
        FROM event_exports
        WHERE event_id=? AND user_id=? AND export_format=?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (event_id, user_id, EXPORT_FORMAT),
    ).fetchone()
    return _export_public(row) if row else None


def event_completion_status(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    user_id: str,
) -> dict[str, Any]:
    event = conn.execute(
        "SELECT * FROM events WHERE id=? AND user_id=?",
        (event_id, user_id),
    ).fetchone()
    if not event:
        raise KeyError("event_not_found")

    photos = conn.execute(
        """
        SELECT id,original_name,status
        FROM photos
        WHERE event_id=?
        ORDER BY created_at ASC
        """,
        (event_id,),
    ).fetchall()
    photo_ids = [str(row["id"]) for row in photos]
    total = len(photo_ids)

    predictions = _latest_predictions_by_photo(
        conn,
        event_id=event_id,
        user_id=user_id,
    )
    decisions = _latest_current_decisions_by_photo(
        conn,
        event_id=event_id,
        user_id=user_id,
    )

    approved = sum(
        1 for item in decisions.values()
        if item.get("verdict") == "approved"
    )
    corrected = sum(
        1 for item in decisions.values()
        if item.get("verdict") == "corrected"
    )

    predicted_ids = set(predictions)
    decided_ids = set(decisions)
    photo_id_set = set(photo_ids)

    missing_prediction_ids = photo_id_set - predicted_ids
    missing_decision_ids = photo_id_set - decided_ids

    missing_predictions = [
        row["original_name"]
        for row in photos
        if row["id"] in missing_prediction_ids
    ][:12]
    missing_decisions = [
        row["original_name"]
        for row in photos
        if row["id"] in missing_decision_ids
    ][:12]

    ready = bool(total > 0 and len(missing_decision_ids) == 0)
    fingerprint = _decision_fingerprint(decisions) if ready else ""

    latest_export = latest_event_export(
        conn,
        event_id=event_id,
        user_id=user_id,
    )
    export_up_to_date = bool(
        latest_export
        and ready
        and latest_export.get("decision_fingerprint") == fingerprint
        and latest_export.get("status") == "ready"
    )

    return {
        "event_id": event_id,
        "event_name": event["name"],
        "event_status": event["status"],
        "total_photos": total,
        "predicted_photos": len(predicted_ids & photo_id_set),
        "decided_photos": len(decided_ids & photo_id_set),
        "approved_photos": approved,
        "corrected_photos": corrected,
        "remaining_predictions": len(missing_prediction_ids),
        "remaining_decisions": len(missing_decision_ids),
        "missing_prediction_names": missing_predictions,
        "missing_decision_names": missing_decisions,
        "ready_to_complete": ready,
        "completed": str(event["status"]) == "הושלם",
        "decision_fingerprint": fingerprint or None,
        "latest_export": latest_export,
        "export_up_to_date": export_up_to_date,
    }


def dominant_lightroom_source_metadata(
    *,
    ai_profiles_dir: Path,
    user_id: str,
    source_profile_import_id: str,
    max_rows: int = 1000,
) -> dict[str, Optional[str]]:
    """
    Recover Adobe source metadata from the imported Lightroom dataset.

    This lets legacy FiveK export keep the same Camera Raw Version/CameraProfile
    (e.g. Version 4.5 / ACR 4.4) instead of inventing a modern process version.
    """
    dataset_dir = (
        Path(ai_profiles_dir)
        / user_id
        / source_profile_import_id
        / "dataset"
    )

    counters: dict[str, collections.Counter] = {
        "version": collections.Counter(),
        "process_version": collections.Counter(),
        "camera_profile": collections.Counter(),
    }

    read = 0
    for split in ("train", "validation", "test"):
        path = dataset_dir / f"{split}.jsonl"
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if read >= max_rows:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                settings = row.get("develop_settings") or {}

                version = settings.get("Version")
                process = settings.get("ProcessVersion")
                camera_profile = settings.get("CameraProfile")

                if version not in (None, ""):
                    counters["version"][str(version)] += 1
                if process not in (None, ""):
                    counters["process_version"][str(process)] += 1
                if camera_profile not in (None, ""):
                    counters["camera_profile"][str(camera_profile)] += 1
                read += 1
            if read >= max_rows:
                break

    def top(name: str) -> Optional[str]:
        if not counters[name]:
            return None
        return counters[name].most_common(1)[0][0]

    return {
        "camera_raw_version": top("version"),
        "process_version": top("process_version"),
        "camera_profile": top("camera_profile"),
    }


def _num(
    value: Any,
    *,
    decimals: int = 0,
    signed: bool = False,
) -> str:
    number = float(value)
    if decimals <= 0:
        text = str(int(round(number)))
    else:
        text = f"{number:.{decimals}f}"
    if signed and number > 0:
        text = "+" + text
    return text


def _xmp_attributes_legacy(
    recipe: dict[str, Any],
    *,
    source_name: str,
    adobe_metadata: dict[str, Optional[str]],
) -> dict[str, str]:
    attrs: dict[str, str] = {
        "RawFileName": source_name,
        "HasSettings": "True",
        "HasCrop": "False",
    }

    if adobe_metadata.get("camera_raw_version"):
        attrs["Version"] = str(adobe_metadata["camera_raw_version"])
    if adobe_metadata.get("process_version"):
        attrs["ProcessVersion"] = str(adobe_metadata["process_version"])
    if adobe_metadata.get("camera_profile"):
        attrs["CameraProfile"] = str(adobe_metadata["camera_profile"])

    if "temperature" in recipe or "tint" in recipe:
        attrs["WhiteBalance"] = "Custom"
    if "temperature" in recipe:
        attrs["Temperature"] = _num(recipe["temperature"])
    if "tint" in recipe:
        attrs["Tint"] = _num(recipe["tint"], signed=True)

    if "exposure" in recipe:
        attrs["Exposure"] = _num(recipe["exposure"], decimals=2, signed=True)
    if "contrast" in recipe:
        attrs["Contrast"] = _num(recipe["contrast"], signed=True)

    # In the pre-2012 Camera Raw schema the UI's Blacks control is serialized
    # as crs:Shadows.  Do NOT map canonical modern `shadows` to this field.
    if "blacks" in recipe:
        attrs["Shadows"] = _num(recipe["blacks"])

    if "brightness" in recipe:
        attrs["Brightness"] = _num(recipe["brightness"], signed=True)
    if "fill_light" in recipe:
        attrs["FillLight"] = _num(recipe["fill_light"])
    if "recovery" in recipe:
        attrs["HighlightRecovery"] = _num(recipe["recovery"])
    if "clarity" in recipe:
        attrs["Clarity"] = _num(recipe["clarity"], signed=True)
    if "vibrance" in recipe:
        attrs["Vibrance"] = _num(recipe["vibrance"], signed=True)
    if "saturation" in recipe:
        attrs["Saturation"] = _num(recipe["saturation"], signed=True)

    return attrs


def _xmp_attributes_modern(
    recipe: dict[str, Any],
    *,
    source_name: str,
    adobe_metadata: dict[str, Optional[str]],
) -> dict[str, str]:
    attrs: dict[str, str] = {
        "RawFileName": source_name,
        "HasSettings": "True",
        "HasCrop": "False",
    }

    if adobe_metadata.get("camera_raw_version"):
        attrs["Version"] = str(adobe_metadata["camera_raw_version"])
    if adobe_metadata.get("process_version"):
        attrs["ProcessVersion"] = str(adobe_metadata["process_version"])
    if adobe_metadata.get("camera_profile"):
        attrs["CameraProfile"] = str(adobe_metadata["camera_profile"])

    if "temperature" in recipe or "tint" in recipe:
        attrs["WhiteBalance"] = "Custom"
    if "temperature" in recipe:
        attrs["Temperature"] = _num(recipe["temperature"])
    if "tint" in recipe:
        attrs["Tint"] = _num(recipe["tint"], signed=True)

    mapping = {
        "exposure": ("Exposure2012", 2),
        "contrast": ("Contrast2012", 0),
        "highlights": ("Highlights2012", 0),
        "shadows": ("Shadows2012", 0),
        "whites": ("Whites2012", 0),
        "blacks": ("Blacks2012", 0),
        "clarity": ("Clarity2012", 0),
    }
    for key, (tag, decimals) in mapping.items():
        if key in recipe:
            attrs[tag] = _num(
                recipe[key],
                decimals=decimals,
                signed=True,
            )

    if "vibrance" in recipe:
        attrs["Vibrance"] = _num(recipe["vibrance"], signed=True)
    if "saturation" in recipe:
        attrs["Saturation"] = _num(recipe["saturation"], signed=True)

    return attrs


def build_lightroom_xmp(
    *,
    source_name: str,
    recipe: dict[str, Any],
    process_family: str,
    adobe_metadata: Optional[dict[str, Optional[str]]] = None,
) -> str:
    clean = canonicalize_recipe(recipe or {})
    family = str(process_family or "unknown").strip().lower()
    meta = adobe_metadata or {}

    if family == "legacy":
        attrs = _xmp_attributes_legacy(
            clean,
            source_name=source_name,
            adobe_metadata=meta,
        )
    else:
        attrs = _xmp_attributes_modern(
            clean,
            source_name=source_name,
            adobe_metadata=meta,
        )

    attr_text = "\n".join(
        f'   crs:{escape(str(key))}={quoteattr(str(value))}'
        for key, value in attrs.items()
    )

    return (
        '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="ProGrapher">\n'
        ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '  <rdf:Description rdf:about=""\n'
        '   xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"\n'
        f'{attr_text}>\n'
        '  </rdf:Description>\n'
        ' </rdf:RDF>\n'
        '</x:xmpmeta>\n'
        '<?xpacket end="w"?>\n'
    )


def _readme_text(event_name: str, photo_count: int) -> str:
    return f"""ProGrapher — Lightroom XMP Export
===================================

אירוע: {event_name}
מספר תמונות: {photo_count}

מה יש כאן?
------------
בתיקיית XMP נמצאים קבצי Sidecar בשם זהה לקובץ ה-RAW המקורי:
IMG_0001.CR3  ->  IMG_0001.xmp

איך להשתמש ב-Lightroom Classic?
--------------------------------
1. חלץ את ה-ZIP.
2. העתק את קבצי ה-XMP אל התיקייה שבה נמצאים קבצי ה-RAW המקוריים.
3. ודא שלכל RAW נמצא לידו XMP עם אותו שם בסיס.
4. ב-Lightroom Classic בחר את התמונות.
5. בחר Metadata > Read Metadata from Files.

חשוב
-----
- קובצי ה-RAW המקוריים אינם משתנים.
- ה-XMP מכיל את ה-Recipe הסופי שנבחר ב-ProGrapher.
- בתמונות RAW קנייניות Adobe שומרת הגדרות עריכה ב-Sidecar XMP.
- ב-DNG Lightroom/Camera Raw יכולים לשמור Metadata בתוך הקובץ עצמו; אם ההעדפות שלך
  מוגדרות להתעלם מ-Sidecar עבור DNG, יש לשנות את ההעדפה או לקרוא Metadata במפורש.
- ProGrapher V1 מייצא כרגע רק Controls שכלולים ב-Recipe Contract שלו.
"""


def build_event_xmp_export(
    conn: sqlite3.Connection,
    *,
    data_dir: Path,
    ai_profiles_dir: Path,
    event_id: str,
    user_id: str,
) -> dict[str, Any]:
    status = event_completion_status(
        conn,
        event_id=event_id,
        user_id=user_id,
    )
    if not status["ready_to_complete"]:
        raise RuntimeError(
            f"Event is not ready: {status['remaining_decisions']} photos still need a final decision."
        )

    event = conn.execute(
        "SELECT * FROM events WHERE id=? AND user_id=?",
        (event_id, user_id),
    ).fetchone()
    photos = conn.execute(
        """
        SELECT *
        FROM photos
        WHERE event_id=?
        ORDER BY created_at ASC
        """,
        (event_id,),
    ).fetchall()
    decisions = _latest_current_decisions_by_photo(
        conn,
        event_id=event_id,
        user_id=user_id,
    )

    # XMP sidecars must match original RAW basenames exactly.  Fail loudly on a
    # duplicate basename rather than silently producing a sidecar for the wrong file.
    stems: dict[str, str] = {}
    duplicate_stems: list[str] = []
    for row in photos:
        stem = Path(str(row["original_name"])).stem
        folded = stem.casefold()
        if folded in stems:
            duplicate_stems.append(stem)
        stems[folded] = str(row["original_name"])
    if duplicate_stems:
        raise RuntimeError(
            "Duplicate RAW basenames prevent a safe Lightroom XMP export: "
            + ", ".join(sorted(set(duplicate_stems))[:8])
        )

    export_id = str(uuid.uuid4())
    event_slug = _slug(event["name"], "ProGrapher_Event")
    export_root = (
        Path(data_dir)
        / "events"
        / event_id
        / "exports"
        / export_id
    )
    xmp_dir = export_root / "XMP"
    xmp_dir.mkdir(parents=True, exist_ok=True)

    registry_meta_cache: dict[str, dict[str, Optional[str]]] = {}
    manifest_photos = []
    profile_versions = set()
    approved_count = 0
    corrected_count = 0

    for photo in photos:
        photo_id = str(photo["id"])
        decision = decisions.get(photo_id)
        if not decision:
            raise RuntimeError(f"Missing final decision for {photo['original_name']}")

        registry_id = str(decision["registry_id"])
        if registry_id not in registry_meta_cache:
            registry = conn.execute(
                """
                SELECT *
                FROM ai_profile_registries
                WHERE id=? AND user_id=?
                """,
                (registry_id, user_id),
            ).fetchone()
            if not registry:
                raise RuntimeError("AI Profile registry for event decision is missing.")
            registry_meta_cache[registry_id] = dominant_lightroom_source_metadata(
                ai_profiles_dir=Path(ai_profiles_dir),
                user_id=user_id,
                source_profile_import_id=str(registry["source_profile_import_id"]),
            )

        final_recipe = canonicalize_recipe(
            decision.get("photographer_recipe") or {}
        )
        process_family = str(decision.get("process_family") or "unknown")
        xmp = build_lightroom_xmp(
            source_name=str(photo["original_name"]),
            recipe=final_recipe,
            process_family=process_family,
            adobe_metadata=registry_meta_cache[registry_id],
        )

        xmp_name = f"{Path(str(photo['original_name'])).stem}.xmp"
        (xmp_dir / xmp_name).write_text(xmp, encoding="utf-8")

        verdict = str(decision.get("verdict") or "")
        if verdict == "approved":
            approved_count += 1
        elif verdict == "corrected":
            corrected_count += 1

        profile_versions.add(int(decision["profile_version_number"]))
        manifest_photos.append(
            {
                "photo_id": photo_id,
                "raw_file": photo["original_name"],
                "xmp_file": xmp_name,
                "decision_id": decision["id"],
                "verdict": verdict,
                "profile_version": int(decision["profile_version_number"]),
                "recipe_contract_version": decision["recipe_contract_version"],
                "process_family": process_family,
                "final_recipe": final_recipe,
            }
        )

    fingerprint = _decision_fingerprint(decisions)
    created_at = _utc_now()
    manifest = {
        "export_format": EXPORT_FORMAT,
        "export_id": export_id,
        "event_id": event_id,
        "event_name": event["name"],
        "created_at": created_at,
        "photo_count": len(photos),
        "approved_count": approved_count,
        "corrected_count": corrected_count,
        "profile_versions": sorted(profile_versions),
        "decision_fingerprint": fingerprint,
        "xmp_notes": {
            "raw_files_modified": False,
            "canonical_recipe_is_source_of_truth": True,
            "legacy_blacks_serialized_as_crs_shadows": True,
        },
        "photos": manifest_photos,
    }

    (export_root / "ProGrapher_export_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (export_root / "README_HE.txt").write_text(
        _readme_text(str(event["name"]), len(photos)),
        encoding="utf-8",
    )

    zip_name = f"ProGrapher_{event_slug}_Lightroom_XMP.zip"
    zip_path = export_root / zip_name
    archive_root = f"{event_slug}_ProGrapher_XMP"

    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for path in sorted(xmp_dir.glob("*.xmp")):
            archive.write(
                path,
                f"{archive_root}/XMP/{path.name}",
            )
        archive.write(
            export_root / "ProGrapher_export_manifest.json",
            f"{archive_root}/ProGrapher_export_manifest.json",
        )
        archive.write(
            export_root / "README_HE.txt",
            f"{archive_root}/README_HE.txt",
        )

    rel_path = zip_path.relative_to(Path(data_dir)).as_posix()

    conn.execute(
        """
        INSERT INTO event_exports (
            id,event_id,user_id,export_format,status,file_path,file_name,
            photo_count,approved_count,corrected_count,profile_versions_json,
            decision_fingerprint,manifest_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            export_id,
            event_id,
            user_id,
            EXPORT_FORMAT,
            "ready",
            rel_path,
            zip_name,
            len(photos),
            approved_count,
            corrected_count,
            json.dumps(sorted(profile_versions)),
            fingerprint,
            json.dumps(manifest, ensure_ascii=False),
            created_at,
        ),
    )

    conn.execute(
        """
        UPDATE events
        SET status='הושלם', updated_at=?
        WHERE id=? AND user_id=?
        """,
        (created_at, event_id, user_id),
    )
    conn.execute(
        """
        UPDATE photos
        SET status='הושלם', updated_at=?
        WHERE event_id=?
        """,
        (created_at, event_id),
    )

    row = conn.execute(
        "SELECT * FROM event_exports WHERE id=?",
        (export_id,),
    ).fetchone()
    return _export_public(row)
