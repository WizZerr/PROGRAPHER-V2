// Pure helpers for the Lightroom event panel (no React, no network) so they can be unit-tested with node --test.

export type EventFolder = {
  key: string;
  label: string;
  path: string;
  photos: number;
  first: string;
  last: string;
};

export type JobStatus =
  | "pending"
  | "planning"
  | "planned"
  | "queued"
  | "writing"
  | "completed"
  | "failed"
  | "outdated"
  | "interrupted"
  | "cancelled"
  | "undone"
  | "partially_undone";

export type Blocking = { reason: string; edited?: number; required?: number };

export type EventJob = {
  job_id: string;
  kind: "anchors" | "complete" | "undo";
  status: JobStatus;
  event_id: string;
  progress: { done: number; total: number; phase?: string | null };
  error: string | null;
  plan: Record<string, unknown> & { blocking?: Blocking[] } | null;
  result: Record<string, unknown> | null;
  parent_job: string | null;
};

const ACTIVE: JobStatus[] = ["pending", "planning", "queued", "writing"];

export function isActive(status: JobStatus): boolean {
  return ACTIVE.includes(status);
}

/** A plan may be confirmed only once it is planned and nothing blocks it. */
export function canConfirm(job: EventJob | null): boolean {
  return !!job && job.status === "planned" && !(job.plan?.blocking?.length);
}

/** Planning again is offered only when the engine knows nothing was written; otherwise the catalog must be
 *  checked against the backup first (a crash after COMMIT, or a state it could not verify). */
export function canRetry(job: EventJob | null): boolean {
  if (!job) return false;
  if (["outdated", "interrupted", "cancelled"].includes(job.status)) return true;
  return job.status === "failed" && job.result?.nothing_written === true;
}

/** What a running job is doing, with its progress. */
export function progressText(job: EventJob): string {
  const { done, total, phase } = job.progress;
  const count = total ? ` ${done.toLocaleString("he-IL")} / ${total.toLocaleString("he-IL")}` : "";
  if (isActive(job.status) && phase === "learning") return `לומד את הסגנון מהפרופיל…${count}`;
  if (isActive(job.status) && phase === "measuring") return `מנתח את תמונות האירוע…${count}`;
  if (isActive(job.status) && phase === "matching") return `מחפש את ה-Smart Previews של התמונות…${count}`;
  return `${statusText(job.status)}${count}`;
}

const EXPOSURE_REASON: Record<string, string> = {
  no_smart_previews: "אין Smart Previews לתמונות האירוע",
  smart_previews_not_matched: "לא נמצאה התאמה בין ה-Smart Previews לתמונות האירוע",
  face_model_missing: "קובץ זיהוי הפנים לא מותקן",
  decoder_unavailable: "פענוח ה-Smart Previews לא זמין",
  profile_has_no_face_style: "בפרופיל אין מספיק תמונות עם פנים",
  too_few_faces_in_event: "נמצאו מעט מדי פנים באירוע",
};

/** How the exposure of an automatic plan was decided. */
export function exposureText(exposure: {
  mode?: string; reason?: string | null; level?: number; faces?: number; measured?: number;
}): string {
  if (exposure.mode === "faces") {
    return `חשיפה לכל תמונה לפי הפנים בה (נמצאו פנים ב-${(exposure.faces ?? 0).toLocaleString("he-IL")} תמונות).`;
  }
  if (exposure.reason === "too_few_faces_in_event" && typeof exposure.measured === "number") {
    return `חשיפה אחידה לפי הפרופיל, כי מתוך ${exposure.measured.toLocaleString("he-IL")} תמונות שנבדקו נמצאו מעט מדי פנים.`;
  }
  const why = EXPOSURE_REASON[exposure.reason ?? ""] ?? "";
  const level = typeof exposure.level === "number" ? ` (${exposure.level > 0 ? "+" : ""}${exposure.level})` : "";
  return `חשיפה אחידה לפי הפרופיל${level}${why ? `, כי ${why}` : ""}.`;
}

export function statusText(status: JobStatus): string {
  switch (status) {
    case "pending":
    case "planning":
      return "בודק את הקטלוג (בלי לשנות דבר)…";
    case "planned":
      return "הבדיקה מוכנה. שום דבר עוד לא נכתב.";
    case "queued":
    case "writing":
      return "כותב לקטלוג…";
    case "completed":
      return "בוצע.";
    case "failed":
      return "נכשל.";
    case "outdated":
      return "האירוע השתנה מאז הבדיקה. לא נכתב דבר; יש לבדוק מחדש.";
    case "interrupted":
      return "הפעולה נקטעה לפני כתיבה. לא נכתב דבר.";
    case "cancelled":
      return "בוטל לפני כתיבה.";
    case "undone":
      return "בוטל: הקטלוג הוחזר.";
    case "partially_undone":
      return "בוטל חלקית: תמונות שערכת אחרי ProGrapher נשארו כמו שהן.";
  }
}

const SKIP_TEXT: Record<string, string> = {
  no_edited_anchor_in_moment: "אין ברגע שלהן תמונה שערכת",
  light_differs_from_anchor: "האור שונה מהתמונה שערכת ברגע",
  white_balance_unknown: "איזון הלבן של המצלמה לא ידוע",
  already_up_to_date: "כבר בערכים האלה",
  nothing_to_write: "אין מה לשנות",
  edited_by_photographer: "כבר ערוכות (לא נוגעים)",
  changed_after_prographer: "ערכת אותן אחרי ProGrapher",
};

export function skipText(reason: string): string {
  return SKIP_TEXT[reason] ?? reason;
}

export function blockingText(block: Blocking): string {
  if (block.reason === "nothing_to_write") return "אין מה לכתוב: כל התמונות באירוע כבר ערוכות או כבר בערכים האלה.";
  if (block.reason === "too_few_edited_anchors") {
    return `ערכת ${block.edited ?? 0} מתוך ${block.required ?? 0} התמונות הנדרשות לפחות. ערוך עוד תמונות מה-Collection ובדוק שוב.`;
  }
  return block.reason;
}

const SLIDER_TEXT: Record<string, string> = {
  Exposure2012: "Exposure",
  Contrast2012: "Contrast",
  Highlights2012: "Highlights",
  Shadows2012: "Shadows",
  Whites2012: "Whites",
  Blacks2012: "Blacks",
  Texture: "Texture",
  Clarity2012: "Clarity",
  Dehaze: "Dehaze",
  Vibrance: "Vibrance",
  Saturation: "Saturation",
  Temperature: "Temp",
  Tint: "Tint",
};

export function sliderList(keys: string[]): string {
  return keys.map((k) => SLIDER_TEXT[k] ?? k).join(", ");
}

/** Skip reasons sorted by count, as "reason: n" lines in Hebrew. */
export function skipLines(skipped: Record<string, number> | undefined): string[] {
  return Object.entries(skipped ?? {})
    .sort((a, b) => b[1] - a[1])
    .map(([reason, count]) => `${skipText(reason)}: ${count.toLocaleString("he-IL")}`);
}

export function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export type SavedEvent = {
  catalogPath: string;
  folderKeys: string[];
  profileId: string | null;
  completeJob: string | null;
  undoJob: string | null;
};

export function parseSaved(raw: string | null): SavedEvent | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<SavedEvent>;
    if (typeof value.catalogPath !== "string" || !Array.isArray(value.folderKeys)) return null;
    return {
      catalogPath: value.catalogPath,
      folderKeys: value.folderKeys.filter((k): k is string => typeof k === "string"),
      profileId: typeof value.profileId === "string" ? value.profileId : null,
      completeJob: typeof value.completeJob === "string" ? value.completeJob : null,
      undoJob: typeof value.undoJob === "string" ? value.undoJob : null,
    };
  } catch {
    return null;
  }
}
