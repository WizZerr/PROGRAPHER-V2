"""RAW-CAT-01F.03C — LOCAL-ONLY original RAW visual annotation contact sheet.

No edits, model, cloud, image upload, Lightroom previews or targets. Creates
neutral, approximate previews from approved source RAWs only, strictly LOCAL.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.brain_v2.preprocessing.raw_decode import decode_raw, deterministic_sample
from app.photographer.raw_catalog_intake import _write_atomic

SCHEMA = "prographer.raw_local_photo_review.v1"
MAX_ITEMS = 24
SCENE_OPTIONS = (
    ("UNKNOWN", "לא ידוע"),
    ("DAYLIGHT_OUTDOOR", "חוץ / אור יום"),
    ("INDOOR_AMBIENT", "פנים / תאורה רגילה"),
    ("DIM_RECEPTION", "אולם או קבלת פנים חשוכים"),
    ("SATURATED_STAGE_MIXED", "תאורה צבעונית / מעורבת"),
    ("OTHER", "אחר"),
)
REVIEW_OPTIONS = (
    ("UNKNOWN", "לא אומת"),
    ("YES", "כן"),
    ("NO", "לא"),
)


def _display_thumbnail(linear: np.ndarray) -> Image.Image:
    """Approximate display sRGB for visual labels; NOT Adobe RAW parity."""
    rgb = deterministic_sample(linear, max_pixels=450_000)
    if rgb.ndim != 3 or rgb.shape[-1] != 3 or rgb.size == 0:
        raise ValueError("invalid RGB frame")
    if not np.isfinite(rgb).all() or float(rgb.min()) < 0 or float(rgb.max()) > 1:
        raise ValueError("nonfinite/out-of-bounds RGB frame")
    clipped = np.asarray(rgb, dtype=np.float32)
    srgb = np.where(
        clipped <= 0.0031308, 12.92 * clipped,
        1.055 * np.power(clipped, 1 / 2.4) - 0.055,
    )
    img = Image.fromarray(np.rint(np.clip(srgb, 0, 1) * 255).astype(np.uint8), mode="RGB")
    img.thumbnail((820, 550), Image.Resampling.LANCZOS)
    return img


def _options(options: tuple[tuple[str, str], ...]) -> str:
    return "".join(
        f'<option value="{escape(key, quote=True)}">{escape(label)}</option>'
        for key, label in options
    )


def _make_html(cards: list[dict[str, Any]]) -> str:
    markup: list[str] = []
    scenes = _options(SCENE_OPTIONS)
    review = _options(REVIEW_OPTIONS)
    for item in cards:
        filename = escape(item["raw_name"], quote=True)
        group = escape(str(item["group"]), quote=True)
        cid = escape(str(item["catalog_id"]), quote=True)
        sha = escape(item["raw_sha256"], quote=True)
        thumb = escape(item["thumbnail"], quote=True)
        index = item["index"]
        markup.append(f'''
        <article class="photo" data-file="{filename}" data-group="{group}"
                 data-cat="{cid}" data-sha="{sha}">
          <img src="{thumb}" alt="Unedited RAW neutral preview" loading="lazy">
          <div class="info">
            <div class="number">#{index:02d} · קבוצת קטלוג זמנית {group}</div>
            <div class="fname" dir="ltr">{filename}</div>
            <label>סוג הסצנה <select class="scene">{scenes}</select></label>
            <label>אירוע אמיתי (מזהה שתבחרו) <input class="event" type="text" placeholder="יש לאמת מול הצלם"></label>
            <label>זהות RAW ↔ רשומת Lightroom <select class="identity">{review}</select></label>
            <label>עריכת Lightroom סופית ואושרה <select class="finality">{review}</select></label>
            <label>הערות / סצנה מיוחדת <textarea class="notes" rows="2" placeholder="לא חובה"></textarea></label>
          </div>
        </article>''')
    body = "\n".join(markup)
    return """<!doctype html>
<html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ProGrapher · סקירת תמונות מקור</title>
<style>
:root{color-scheme:dark;font:15px/1.55 system-ui,"Segoe UI",Arial,sans-serif;background:#101216;color:#f1f2f5}
*{box-sizing:border-box}body{margin:0;min-height:100vh}
header{padding:28px max(20px,calc((100% - 1450px)/2));border-bottom:1px solid #343841;background:#17191f}
h1{margin:0;font-size:26px;font-weight:650;letter-spacing:-.5px}header p{color:#b7bdc7;margin:9px 0 0}
main{max-width:1450px;margin:auto;padding:22px}
.toolbar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:0 0 23px}
button{background:#e8eef9;color:#171b24;border:0;border-radius:9px;padding:12px 20px;font:inherit;font-weight:650;cursor:pointer}
button:hover{background:#fff}.warn{color:#ffce91;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px}
.photo{overflow:hidden;background:#1c1f26;border:1px solid #363b45;border-radius:13px}
.photo img{width:100%;height:260px;object-fit:contain;background:#0a0b0e;display:block}
.info{padding:18px}.number{color:#a6b0c5;font-size:13px}
.fname{font-weight:600;font-size:14px;margin:5px 0 13px;text-align:right}
label{display:block;color:#d4d9e2;font-size:13px;margin:11px 0}
input,select,textarea{width:100%;display:block;margin-top:5px;padding:9px 10px;
border:1px solid #414853;border-radius:7px;background:#12151b;color:#f7f8fa;font:inherit}
textarea{resize:vertical}footer{color:#aab1bb;padding:30px;text-align:center}
</style></head><body>
<header><h1>ProGrapher — סקירת מקור RAW</h1><p>
הדמיה מקומית בלבד מתוך קובצי RAW מקוריים. הצבעים והבהירות בקירוב, לא עיבוד Lightroom.
התמונות אינן מועלות לאינטרנט. הסימונים יישמרו רק לאחר לחיצה על ייצוא CSV פרטי.</p></header>
<main><div class="toolbar"><button type="button" id="export">ייצוא סימוני הצלם ל־CSV פרטי</button>
<span id="status" class="warn">ברירת המחדל: UNKNOWN. שום תמונה אינה מאושרת לאימון.</span></div>
<section class="grid">""" + body + """</section></main>
<footer>לשמירה מקומית בלבד · יש לאמת אירועים ועריכות בתוך Lightroom · אין להעלות תמונות או דוח CSV ציבורית</footer>
<script>
(function(){
"use strict";
function cell(v) {
  var s=String(v==null?"":v);
  if (/^[\\s]*[=+@-]/.test(s)) s="'"+s;
  return '"'+s.replace(/"/g,'""')+'"';
}
document.getElementById("export").addEventListener("click",function(){
  var head=["raw_name","provisional_catalog_group","catalog_image_id","raw_sha256",
    "scene_label","event_id","raw_identity_verified_by_photographer",
    "final_edit_confirmed_by_photographer","notes"];
  var rows=[head];
  document.querySelectorAll(".photo").forEach(function(el){
    rows.push([el.dataset.file,el.dataset.group,el.dataset.cat,el.dataset.sha,
      el.querySelector(".scene").value,el.querySelector(".event").value.trim(),
      el.querySelector(".identity").value,el.querySelector(".finality").value,
      el.querySelector(".notes").value.trim()]);
  });
  var csv="\\uFEFF"+rows.map(function(r){return r.map(cell).join(",");}).join("\\r\\n");
  var url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  var a=document.createElement("a");a.href=url;a.download="RAW_CAT_01F_03C_REVIEW_PRIVATE.csv";
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(function(){URL.revokeObjectURL(url)},1000);
  document.getElementById("status").textContent="קובץ CSV נוצר. הוא מכיל נתוני תמונות פרטיים — שמרו אותו מקומית בלבד.";
});
})();
</script></body></html>"""


def build_review(private_manifest: Path, raw_root: Path, output_dir: Path) -> dict:
    if not raw_root.is_dir():
        raise ValueError("RAW directory not found")
    manifest = json.loads(private_manifest.read_text(encoding="utf-8"))
    records = manifest.get("records")
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_ITEMS:
        raise ValueError("expected 1..24 private research records")
    if manifest.get("all_model_inputs_are_RAW_only") is not True:
        raise ValueError("unsupported manifest: original RAW-only inputs required")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output review directory must be new or empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    cards: list[dict] = []
    errors: Counter[str] = Counter()
    for index, row in enumerate(records, 1):
        try:
            source = row["provenance_PRIVATE"]
            raw = Path(source["raw_path"]).resolve(strict=True)
            if (not raw.is_relative_to(raw_root) or raw.suffix.lower() != ".cr3"
                    or raw.name.startswith("._") or raw.is_symlink() or not raw.is_file()):
                raise ValueError("unsafe RAW source path")
            if (not isinstance(source["raw_sha256"], str)
                    or len(source["raw_sha256"]) != 64):
                raise ValueError("missing original source hash")
            frame = decode_raw(raw)
            if frame.source_sha256 != source["raw_sha256"]:
                raise ValueError("RAW source changed since 03B pilot")
            thumb = f"source_preview_{index:02d}.jpg"
            _display_thumbnail(frame.rgb_linear).save(
                output_dir / thumb, format="JPEG", quality=85
            )
            cards.append({
                "index": index,
                "raw_name": raw.name,
                "raw_sha256": frame.source_sha256,
                "group": source.get("provisional_catalog_group") or "UNKNOWN",
                "catalog_id": source.get("catalog_image_id") or "",
                "thumbnail": thumb,
            })
            del frame
        except (OSError, ValueError, KeyError, RuntimeError, MemoryError) as exc:
            # No exception details or photo identifiers go to shareable report.
            errors[type(exc).__name__] += 1
    (output_dir / "REVIEW_PRIVATE.html").write_text(_make_html(cards), encoding="utf-8")
    return {
        "schema": SCHEMA,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PRIVATE_SOURCE_ONLY_HUMAN_REVIEW_NOT_TRAINING",
        "privacy": "AGGREGATE ONLY: keep REVIEW_PRIVATE.html, derived previews and annotation CSV LOCAL",
        "requested": len(records),
        "thumbnails_created": len(cards),
        "failed": dict(sorted(errors.items())),
        "labels_confirmed": 0,
        "events_confirmed": 0,
        "final_edits_confirmed": 0,
        "training_ready": 0,
        "warning": "Approximate source-RAW visualization, not Adobe pixel parity or scene-classifier prediction",
    }


def main() -> int:
    cli = argparse.ArgumentParser(description="Local-only original RAW human annotation contact sheet")
    cli.add_argument("--private-manifest", type=Path, required=True)
    cli.add_argument("--raw-dir", type=Path, required=True)
    cli.add_argument("--out-dir", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    cli.add_argument("--consent-acknowledged", action="store_true")
    args = cli.parse_args()
    if not args.consent_acknowledged:
        cli.error("Photographer permission for local RAW visual review is required")
    try:
        root = args.raw_dir.expanduser().resolve(strict=True)
        manifest = args.private_manifest.expanduser().resolve(strict=True)
        out = args.out_dir.expanduser().resolve()
        report_path = args.report.expanduser().resolve()
        if (out.is_relative_to(root) or report_path.is_relative_to(root)
                or report_path == manifest or report_path.is_relative_to(out)
                or out == manifest or out == root):
            raise ValueError("review outputs must be outside RAW originals; no overwrites")
        report = build_review(manifest, root, out)
        _write_atomic(report_path, report)
    except (OSError, ValueError, RuntimeError, MemoryError) as exc:
        cli.exit(2, f"RAW PHOTO REVIEW FAILED: {type(exc).__name__}: {exc}\n")
    print("Local review HTML:", out / "REVIEW_PRIVATE.html")
    print("AGGREGATE report:", report_path)
    print("Neutral source previews:", report["thumbnails_created"])
    print("Failed:", sum(report["failed"].values()))
    print("Training eligible: 0 (review required)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
