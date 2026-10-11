"""RAW-CAT-01F.03D: locally suggested wedding-scene labels from ORIGINAL RAW only.

CLIP is zero-shot research, NOT a calibrated scene classifier. Download MODEL
WEIGHTS only with explicit --allow-model-download. Photos never go to network.
Every guess requires human confirmation; no photo becomes training-ready.
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

from app.brain_v2.preprocessing.raw_decode import decode_raw
from app.photographer.raw_catalog_intake import _write_atomic
from app.photographer.raw_local_review import _display_thumbnail
from app.photographer.raw_visual_context_probe import describe_linear_rgb

MODEL_ID = "openai/clip-vit-base-patch32"
SCHEMA = "prographer.raw_auto_scene_review.v0"
SCENE_CHOICES = (
    ("UNKNOWN", "לא בטוח / לא יודע"),
    ("GETTING_READY", "התארגנות / איפור"),
    ("CEREMONY", "טקס / חופה"),
    ("DANCING", "רחבת ריקודים"),
    ("PORTRAIT", "דיוקן זוגי / יחיד"),
    ("GROUP_PORTRAIT", "תמונה קבוצתית מבוימת"),
    ("RECEPTION", "אורחים / קבלת פנים"),
    ("DETAILS", "פרטים / עיצוב / שולחנות"),
    ("OTHER", "אחר"),
)
# Natural-language descriptions used ONLY against ORIGINAL camera RAW previews.
PROMPTS = (
    "A wedding photographer's photo of a bride having her hair and makeup done in a preparation room.",
    "A wedding photographer's photo of the wedding ceremony beneath a wedding canopy or chuppah.",
    "A wedding photographer's photo of guests dancing on a crowded wedding dance floor.",
    "A wedding photographer's artistic portrait of a bride, groom, or couple.",
    "A wedding photographer's posed group portrait of people facing a camera.",
    "A wedding photographer's candid photo of wedding guests socializing at a reception.",
    "A wedding photographer's detailed closeup of wedding decorations, flowers, rings, or a dining table.",
    "A photograph of something unrelated to a wedding or event.",
)
# Align prompt classes with SCENE_CHOICES excluding UNKNOWN; OTHER is the 8th.
PROMPT_KEYS = tuple(k for k, _ in SCENE_CHOICES if k != "UNKNOWN")
MAX_ITEMS = 24


def _rank_relative(scores: list[float]) -> dict[str, Any]:
    """Relative softmax/ranking within the prompt set. NOT calibrated confidence."""
    if len(scores) != len(PROMPT_KEYS) or not np.all(np.isfinite(scores)):
        raise ValueError("invalid relative model scores")
    if any(score < 0 for score in scores) or abs(sum(scores) - 1) > 1e-3:
        raise ValueError("scores must be a normalized relative distribution")
    ordered = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)
    a, b = ordered[:2]
    top = float(scores[a])
    margin = top - float(scores[b])
    # Conservative abstention on score or runner-up margin. These are
    # arbitrary REVIEW heuristics, NOT empirically calibrated thresholds.
    abstain = top < 0.31 or margin < 0.12 or PROMPT_KEYS[a] == "OTHER"
    return {
        "raw_top_label": PROMPT_KEYS[a],
        "suggested_label": "UNKNOWN" if abstain else PROMPT_KEYS[a],
        "relative_top_score": round(top, 4),
        "relative_margin": round(margin, 4),
        "abstained": abstain,
    }


def _lighting_indicator(features: dict[str, float]) -> str:
    """Technical decoded linear RAW brightness indicator, NOT scene diagnosis."""
    dark = features["fraction_luminance_below_0_03"]
    if dark > 0.72:
        return "RAW כהה מאוד"
    if dark > 0.40:
        return "RAW כהה יחסית"
    if dark < 0.17:
        return "RAW בהיר יחסית"
    return "תאורה מעורבת או לא חד-משמעית"


class LocalClip:
    """Run a downloaded CLIP zero-shot model on PIL images, ON THIS COMPUTER."""
    def __init__(self, *, allow_model_download: bool = False):
        try:
            import torch
            from transformers import AutoProcessor, AutoModelForZeroShotImageClassification
        except ImportError as exc:
            raise RuntimeError(
                "Install model runtime in venv: python -m pip install -r requirements-phase11-vision.txt"
            ) from exc
        try:
            self.processor = AutoProcessor.from_pretrained(
                MODEL_ID, local_files_only=not allow_model_download
            )
            self.model = AutoModelForZeroShotImageClassification.from_pretrained(
                MODEL_ID, local_files_only=not allow_model_download, use_safetensors=True
            )
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                "Vision model is not cached. If you approve the ~605 MB one-time "
                "MODEL-ONLY download, rerun with --allow-model-download. "
                "This never uploads your photos."
            ) from exc
        self.model.eval()
        self.torch = torch

    def predict(self, original_raw_preview: Image.Image) -> dict[str, Any]:
        inputs = self.processor(
            text=PROMPTS, images=original_raw_preview.convert("RGB"),
            return_tensors="pt", padding=True,
        )
        with self.torch.inference_mode():
            logits = self.model(**inputs).logits_per_image[0]
            scores = self.torch.softmax(logits, dim=-1).detach().cpu().tolist()
        return _rank_relative([float(v) for v in scores])


def _scene_options(current: str) -> str:
    return "".join(
        f'<option value="{escape(key, quote=True)}"'
        + (" selected" if key == current else "")
        + f'>{escape(label)}</option>'
        for key, label in SCENE_CHOICES
    )


def _render(cards: list[dict[str, Any]]) -> str:
    tiles: list[str] = []
    for item in cards:
        name = escape(item["name"], quote=True)
        hash_ = escape(item["sha"], quote=True)
        scene = escape(item["guess"]["raw_top_label"], quote=True)
        proposed = escape(item["guess"]["suggested_label"], quote=True)
        group = escape(str(item["group"]), quote=True)
        cat = escape(str(item["catalog_id"]), quote=True)
        description = dict(SCENE_CHOICES)[item["guess"]["raw_top_label"]]
        guess_text = escape(description)
        uncertainty = (
            "לא מספיק בטוח — כדאי לבדוק" if item["guess"]["abstained"]
            else "הצעה אוטומטית — דורשת אישור אנושי"
        )
        score = item["guess"]["relative_top_score"]
        margin = item["guess"]["relative_margin"]
        light = escape(item["light"])
        tiles.append(f'''
        <article class="photo" data-name="{name}" data-sha="{hash_}"
                 data-group="{group}" data-cat="{cat}" data-top="{scene}"
                 data-suggestion="{proposed}" data-score="{score}" data-margin="{margin}">
          <img src="preview_{item['index']:02d}.jpg" alt="Unedited camera RAW approximate preview" loading="lazy">
          <div class="content">
            <div class="label">#{item['index']:02d} · קבוצת קטלוג זמנית {group}</div>
            <div class="filename" dir="ltr">{name}</div>
            <div class="inference">
              <div class="subhead">הצעת מודל הראייה</div>
              <div class="guess">{guess_text}</div>
              <div class="muted">{escape(uncertainty)}</div>
              <div class="muted">דירוג יחסי: {score:.0%} · פער מדורג שני: {margin:.0%} · <b>לא הסתברות אמיתית</b></div>
              <div class="light">מדידת תאורה: {light}</div>
            </div>
            <label>מה באמת רואים? <select class="scene">{_scene_options('UNKNOWN')}</select></label>
            <label>האם ההצעה נכונה?
              <select class="decision">
                <option value="UNREVIEWED">לא בדקתי עדיין</option>
                <option value="AGREE">כן, ההצעה נכונה</option>
                <option value="CORRECTED">לא, תיקנתי למעלה</option>
                <option value="UNSURE">לא בטוח</option>
              </select>
            </label>
            <label>מזהה אירוע (אם אושר מול הצלם)
              <input class="event" placeholder="אפשר להשאיר ריק">
            </label>
            <label>זהות RAW מול קטלוג Lightroom
              <select class="identity"><option value="UNKNOWN">לא אומת</option>
              <option value="YES">אושר בבדיקה עצמאית</option><option value="NO">לא תואם</option></select>
            </label>
            <label>העריכה סופית לפי הצלם
              <select class="finality"><option value="UNKNOWN">לא אומת</option>
              <option value="YES">הצלם אישר</option><option value="NO">לא</option></select>
            </label>
            <label>הערות <textarea class="notes" rows="2" placeholder="לא חובה"></textarea></label>
          </div>
        </article>''')
    html_start = """<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ProGrapher — AI ראשוני לסקירת RAW</title>
<style>
:root{font:15px/1.55 system-ui,"Segoe UI",Arial,sans-serif;color-scheme:dark;
background:#101217;color:#edf0f5}*{box-sizing:border-box}body{margin:0}
header{background:#171b22;border-bottom:1px solid #323a45;padding:26px max(20px,calc((100% - 1450px)/2))}
header h1{font-weight:680;font-size:25px;letter-spacing:-.4px;margin:0 0 9px}
header p{margin:0;color:#bac3d1;max-width:1100px}
main{max-width:1450px;margin:auto;padding:22px}
.notice{padding:15px 17px;background:#222834;border:1px solid #49556c;border-radius:11px;margin-bottom:20px}
.notice b{color:#f2d394}button{border:0;border-radius:9px;padding:12px 17px;
font:inherit;font-weight:650;background:#e5ebf6;color:#11151d;cursor:pointer}
button:hover{background:#fff}
.toolbar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:0 0 22px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(345px,1fr));gap:18px}
.photo{border:1px solid #363e4b;border-radius:13px;overflow:hidden;background:#1c2029}
.photo img{width:100%;height:285px;object-fit:contain;background:#080a0d;display:block}
.content{padding:18px}.label{font-size:12px;color:#a7b2c3}
.filename{text-align:right;font-size:14px;font-weight:600;margin:5px 0 12px}
.inference{border-radius:10px;background:#131c25;border:1px solid #304251;padding:13px 14px;margin-bottom:15px}
.subhead{font-size:12px;color:#b9c6d8}.guess{font-size:18px;font-weight:680;color:#f0f7ff}
.muted{font-size:12px;color:#abbacd;margin-top:2px}.light{margin-top:10px;color:#addad1;font-size:13px}
label{display:block;color:#d0d9e3;font-size:13px;margin:12px 0}
select,input,textarea{width:100%;border:1px solid #455062;background:#10151c;color:#f7f9fb;
border-radius:8px;padding:9px 11px;font:inherit;display:block;margin-top:5px}
textarea{resize:vertical}footer{text-align:center;color:#a9b4c4;padding:32px}
</style></head><body><header>
<h1>ProGrapher · המערכת מציעה, הצלם מאשר</h1>
<p>הצעות סצנה של מודל ראייה מקומי מתוך RAW מקורי בלבד. הציון הוא דירוג יחסי ולא ביטחון מכויל.
האבחנות עלולות לטעות. אף תיוג לא הופך לאמת או לדוגמת אימון בלי סקירה ואישור.</p>
</header><main>
<div class="notice"><b>לפני שמתחילים:</b> בחרו את סוג הסצנה רק אם היא ברורה.
בשדה "האם ההצעה נכונה" בחרו "כן" רק לאחר בדיקה עצמית. לא חייבים להבין בצילום:
אם לא ברור, השאירו "לא בטוח". שדות זהות הקטלוג וסופיות העריכה דורשים אימות מול הצלם.</div>
<div class="toolbar"><button id="export" type="button">ייצוא CSV סקירה פרטי</button>
<span id="status">הסימונים נשמרים רק אחרי ייצוא. אל תעלו CSV זה ל־GitHub.</span></div>
<div class="grid">"""
    html_end = """</div></main><footer>מקורות RAW נשארים במחשב · הצעות AI למחקר בלבד · אין אימון או העלאת תמונות</footer>
<script>
(function(){
"use strict";
function csvCell(value){
  var s=String(value==null?"":value);
  if (/^[\\s]*[=+@-]/.test(s)) s="'"+s;
  return '"'+s.replace(/"/g,'""')+'"';
}
document.getElementById("export").addEventListener("click",function(){
  var rows=[["raw_name","raw_sha256","catalog_image_id","provisional_group",
    "model_id","auto_top_label","auto_proposed_label","auto_relative_score",
    "auto_relative_margin","human_scene_label","human_review_decision",
    "event_id","catalog_identity_checked","photographer_final_edit_checked","notes"]];
  document.querySelectorAll(".photo").forEach(function(card){
    rows.push([card.dataset.name,card.dataset.sha,card.dataset.cat,card.dataset.group,
      "openai/clip-vit-base-patch32",card.dataset.top,card.dataset.suggestion,
      card.dataset.score,card.dataset.margin,card.querySelector(".scene").value,
      card.querySelector(".decision").value,card.querySelector(".event").value.trim(),
      card.querySelector(".identity").value,card.querySelector(".finality").value,
      card.querySelector(".notes").value.trim()]);
  });
  var csv="\\uFEFF"+rows.map(function(row){return row.map(csvCell).join(",")}).join("\\r\\n");
  var link=document.createElement("a"),url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  link.href=url;link.download="RAW_CAT_01F_03D_AI_REVIEW_PRIVATE.csv";
  document.body.appendChild(link);link.click();link.remove();
  setTimeout(function(){URL.revokeObjectURL(url)},1000);
  document.getElementById("status").textContent="CSV פרטי נוצר. יש לשמור מקומית; לא להעלות ל־GitHub או לצ'אט.";
});
document.querySelectorAll(".decision").forEach(function(sel){
  sel.addEventListener("change",function(){
    var card=sel.closest(".photo");
    if(sel.value==="AGREE"){
      var candidate=card.dataset.suggestion;
      if(candidate==="UNKNOWN"){
        sel.value="UNSURE";
        card.querySelector(".scene").value="UNKNOWN";
      }else{card.querySelector(".scene").value=candidate;}
    }
  });
});
})();
</script></body></html>"""
    return html_start + "\n".join(tiles) + html_end


def build_auto_review(
    private_manifest: Path, raw_root: Path, output_dir: Path, predictor: Any,
) -> dict[str, Any]:
    """Uses injected local model predictor; never serialize model features/paths in report."""
    if not raw_root.is_dir():
        raise ValueError("RAW directory not found")
    manifest = json.loads(private_manifest.read_text(encoding="utf-8"))
    rows = manifest.get("records")
    if manifest.get("all_model_inputs_are_RAW_only") is not True:
        raise ValueError("not a RAW-only private pilot manifest")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ITEMS:
        raise ValueError("private pilot should contain between 1 and 24 RAWs")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be new or empty; existing private review preserved")
    output_dir.mkdir(parents=True, exist_ok=True)
    cards: list[dict[str, Any]] = []
    failures: Counter[str] = Counter()
    ranks: Counter[str] = Counter()
    for index, row in enumerate(rows, 1):
        try:
            source = row["provenance_PRIVATE"]
            raw_path = Path(source["raw_path"])
            # Resolve path while explicitly rejecting symlink files.
            if raw_path.is_symlink():
                raise ValueError("symlink input forbidden")
            raw_path = raw_path.resolve(strict=True)
            if (not raw_path.is_relative_to(raw_root) or raw_path.suffix.lower() != ".cr3"
                    or raw_path.name.startswith("._") or not raw_path.is_file()):
                raise ValueError("unsafe original RAW input")
            frame = decode_raw(raw_path)  # read-only, hash before+after.
            if frame.source_sha256 != source.get("raw_sha256"):
                raise ValueError("original RAW changed since catalog pilot")
            features = describe_linear_rgb(frame.rgb_linear)
            thumb = _display_thumbnail(frame.rgb_linear)
            guess = predictor.predict(thumb)  # source image only
            if not isinstance(guess, dict) or guess.get("suggested_label") not in dict(SCENE_CHOICES):
                raise ValueError("unsupported model prediction")
            thumb.save(output_dir / f"preview_{index:02d}.jpg", format="JPEG", quality=84)
            ranks[guess["suggested_label"]] += 1
            cards.append({
                "index": index,
                "name": raw_path.name,
                "sha": frame.source_sha256,
                "catalog_id": source.get("catalog_image_id") or "",
                "group": source.get("provisional_catalog_group") or "UNKNOWN",
                "guess": guess,
                "light": _lighting_indicator(features),
            })
            del frame
        except (KeyError, ValueError, OSError, RuntimeError, MemoryError) as exc:
            failures[type(exc).__name__] += 1
    (output_dir / "AI_REVIEW_PRIVATE.html").write_text(_render(cards), encoding="utf-8")
    return {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "LOCAL_ZERO_SHOT_SUGGESTIONS_ONLY_UNCALIBRATED_NOT_GROUND_TRUTH",
        "model_id": MODEL_ID,
        "privacy": "AGGREGATE ONLY: local original RAW, derived thumbnails, HTML, private review CSV never uploaded",
        "raw_records_requested": len(rows),
        "suggestions_generated": len(cards),
        "needs_human_review": len(cards),
        "automatic_unknown_count": ranks["UNKNOWN"],
        "predicted_scene_counts_NOT_VERIFIED": dict(sorted(ranks.items())),
        "failures": dict(sorted(failures.items())),
        "human_verified_scene_labels": 0,
        "confirmed_events": 0,
        "lightroom_identity_confirmed": 0,
        "photographer_final_edits_confirmed": 0,
        "training_ready_samples": 0,
        "warning": "CLIP prompt-relative scores are NOT probabilities, model predictions may be wrong; no sample is auto-approved",
    }


def main() -> int:
    cli = argparse.ArgumentParser(description="Local CLIP scene suggestions for original-RAW human review")
    cli.add_argument("--private-manifest", type=Path, required=True)
    cli.add_argument("--raw-dir", type=Path, required=True)
    cli.add_argument("--out-dir", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    cli.add_argument("--consent-acknowledged", action="store_true")
    cli.add_argument("--allow-model-download", action="store_true",
                     help="Download CLIP WEIGHTS (~605 MB) from Hugging Face; RAW photos stay local")
    args = cli.parse_args()
    if not args.consent_acknowledged:
        cli.error("Photographer's explicit local RAW analysis permission required")
    try:
        root = args.raw_dir.expanduser().resolve(strict=True)
        manifest = args.private_manifest.expanduser().resolve(strict=True)
        out_dir = args.out_dir.expanduser().resolve()
        report_path = args.report.expanduser().resolve()
        if (out_dir.is_relative_to(root) or report_path.is_relative_to(root)
            or report_path == manifest or out_dir == manifest
            or report_path.is_relative_to(out_dir) or out_dir == root):
            raise ValueError("outputs must be distinct and outside source/originals")
        predictor = LocalClip(allow_model_download=args.allow_model_download)
        report = build_auto_review(manifest, root, out_dir, predictor)
        _write_atomic(report_path, report)
    except (ValueError, OSError, RuntimeError, MemoryError) as exc:
        cli.exit(2, f"AI REVIEW FAILED (originals unchanged): {type(exc).__name__}: {exc}\n")
    print("Local AI review:", out_dir / "AI_REVIEW_PRIVATE.html")
    print("Aggregate-only report:", report_path)
    print("Scene suggestions:", report["suggestions_generated"])
    print("Uncertain/UNKNOWN:", report["automatic_unknown_count"])
    print("Failed:", sum(report["failures"].values()))
    print("Training-approved: 0 (never automatic)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
