// UI logic of the Lightroom event panel. Run: npm run test:ui (node --test, no browser, no engine).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  blockingText,
  canConfirm,
  canRetry,
  exposureText,
  flashText,
  progressText,
  isActive,
  matchingText,
  parseSaved,
  requiredAcknowledgements,
  skipLines,
  sliderList,
  statusText,
  uniformExposureWarning,
  whiteBalanceText,
  type EventJob,
} from "./eventFlow.ts";

function job(status: EventJob["status"], plan: EventJob["plan"] = {}): EventJob {
  return { job_id: "j", kind: "complete", status, event_id: "e", progress: { done: 0, total: 0 }, error: null, plan,
    result: null, parent_job: null };
}

test("a plan can be confirmed only when planned and not blocked", () => {
  assert.equal(canConfirm(job("planned", { blocking: [] })), true);
  assert.equal(canConfirm(job("planned", { blocking: [{ reason: "too_few_edited_anchors", edited: 1, required: 20 }] })), false);
  for (const status of ["planning", "queued", "writing", "completed", "failed", "outdated", "cancelled"] as const) {
    assert.equal(canConfirm(job(status)), false, status);
  }
  assert.equal(canConfirm(null), false);
});

test("active statuses keep the panel polling; final ones stop it", () => {
  assert.deepEqual(
    (["pending", "planning", "queued", "writing", "planned", "completed", "failed"] as const).map(isActive),
    [true, true, true, true, false, false, false],
  );
});

test("planning again is offered only when nothing was written", () => {
  const failed = (result: EventJob["result"]) => ({ ...job("failed"), result });
  assert.equal(canRetry(failed({ nothing_written: true })), true);
  assert.equal(canRetry(failed({ nothing_written: false })), false);
  assert.equal(canRetry(failed(null)), false);
  assert.equal(canRetry(job("outdated")), true);
  assert.equal(canRetry(job("writing")), false);
  assert.doesNotMatch(statusText("failed"), /לא נכתב/);  // a failure alone does not prove that
});

test("statuses that guarantee no write say so", () => {
  assert.match(statusText("planned"), /לא נכתב/);
  assert.match(statusText("outdated"), /לא נכתב/);
  assert.match(statusText("interrupted"), /לא נכתב/);
});

test("blocking and skip reasons are explained in Hebrew", () => {
  assert.match(blockingText({ reason: "too_few_edited_anchors", edited: 1, required: 20 }), /1 מתוך 20/);
  assert.deepEqual(skipLines({ no_edited_anchor_in_moment: 3, already_up_to_date: 12 }), [
    "כבר בערכים האלה: 12",
    "אין ברגע שלהן תמונה שערכת: 3",
  ]);
  assert.equal(sliderList(["Exposure2012", "Highlights2012", "Temperature"]), "Exposure, Highlights, Temp");
});

test("saved state is validated before use", () => {
  assert.equal(parseSaved(null), null);
  assert.equal(parseSaved("not json"), null);
  assert.equal(parseSaved(JSON.stringify({ folderKeys: [] })), null);
  assert.deepEqual(parseSaved(JSON.stringify({ catalogPath: "C:/a.lrcat", folderKeys: ["k", 3], profileId: 5 })), {
    catalogPath: "C:/a.lrcat", folderKeys: ["k"], profileId: null, completeJob: null, undoJob: null,
  });
});

test("automatic plans explain how exposure was decided and what is running", () => {
  assert.match(exposureText({ mode: "faces", faces: 1200 }), /לפי הפנים/);
  assert.equal(exposureText({ mode: "profile_level", reason: "no_smart_previews", level: -0.35 }),
    "חשיפה אחידה לפי הפרופיל (-0.35), כי אין Smart Previews לתמונות האירוע.");
  const running = { ...job("planning"), progress: { done: 40, total: 400, phase: "learning" } };
  assert.match(progressText(running), /לומד את הסגנון מהפרופיל/);
  assert.match(progressText({ ...running, progress: { done: 5, total: 9, phase: "measuring" } }), /מנתח/);
});

test("a uniform exposure needs its own confirmation before the plan can be written", () => {
  const plan = { blocking: [], requires_acknowledgement: ["uniform_exposure"] };
  assert.deepEqual(requiredAcknowledgements(job("planned", plan)), ["uniform_exposure"]);
  assert.equal(canConfirm(job("planned", plan)), false);
  assert.equal(canConfirm(job("planned", plan), ["something_else"]), false);
  assert.equal(canConfirm(job("planned", plan), ["uniform_exposure"]), true);
  assert.equal(canConfirm(job("writing", plan), ["uniform_exposure"]), false);
  assert.deepEqual(requiredAcknowledgements(job("planned", {})), []);
  assert.match(uniformExposureWarning({ mode: "profile_level", photos: 3184, analysed: 0 }), /אף תמונה/);
  assert.match(uniformExposureWarning({ mode: "faces", photos: 1000, analysed: 600 }), /400 מתוך 1,000/);
});

test("the plan says how many photos were matched to a Smart Preview and why the rest were not", () => {
  assert.equal(matchingText({}), "");
  assert.equal(matchingText({ photos: 10, matching: { by_id: 4, by_name: 4, ambiguous: 0, unmatched: 0 } }).includes("לא"), false);
  const text = matchingText({ photos: 10, matching: { by_id: 2, by_name: 4, ambiguous: 3, unmatched: 1 } });
  assert.match(text, /הותאמו ל-6 מתוך 10/);
  assert.match(text, /ל-1 לא נמצא/);
  assert.match(text, /3 לא הותאמו כי שם הקובץ/);
});

test("the plan shows the profile's flash correction and white-balance rule", () => {
  assert.equal(flashText({}), "");
  assert.equal(flashText({ flash_offsets: { flash: 0.12 }, flash_corrected: 0 }), "");
  assert.equal(flashText({ flash_offsets: { flash: 0.12, no_flash: -0.15 }, flash_corrected: 2865 }),
    "תיקון חשיפה כמו של העורך: עם פלאש +0.12, בלי פלאש −0.15 (ב-2,865 תמונות).");
  assert.equal(whiteBalanceText(undefined), "איזון לבן: נשאר As Shot, כמו שהמצלמה צילמה.");
  assert.equal(whiteBalanceText({ photos: 0 }), "איזון לבן: נשאר As Shot, כמו שהמצלמה צילמה.");
  assert.match(whiteBalanceText({ photos: 446 }), /חוץ מ-446 תמונות/);
});
