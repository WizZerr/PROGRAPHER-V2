// UI logic of the Lightroom event panel. Run: npm run test:ui (node --test, no browser, no engine).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  blockingText,
  canConfirm,
  canRetry,
  isActive,
  parseSaved,
  skipLines,
  sliderList,
  statusText,
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
  assert.deepEqual(parseSaved(JSON.stringify({ catalogPath: "C:/a.lrcat", folderKeys: ["k", 3], anchorsJob: 5 })), {
    catalogPath: "C:/a.lrcat", folderKeys: ["k"], anchorsJob: null, completeJob: null, undoJob: null,
  });
});
