"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  cancelEventJob,
  confirmEventJob,
  getEventJob,
  listCatalogFolders,
  planAnchors,
  planCompletion,
  planUndo,
} from "./eventEdit.api";
import {
  blockingText,
  canConfirm,
  canRetry,
  isActive,
  parseSaved,
  percent,
  skipLines,
  sliderList,
  statusText,
  type EventFolder,
  type EventJob,
  type SavedEvent,
} from "./eventFlow";
import styles from "./LightroomEventPanel.module.css";

const STORAGE_KEY = "pg.lightroomEvent.v2";
const POLL_MS = 400;

export function loadSavedLightroomEvent(): SavedEvent | null {
  try {
    return parseSaved(window.localStorage.getItem(STORAGE_KEY));
  } catch {
    return null;
  }
}

function store(state: SavedEvent | null) {
  try {
    if (state) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // per-viewer convenience only
  }
}

const n = (value: unknown) => Number(value ?? 0).toLocaleString("he-IL");
const fileName = (path: string) => path.split(/[\\/]/).pop() || path;

type Slot = "anchorsJob" | "completeJob" | "undoJob";

export default function LightroomEventPanel({
  catalogPath,
  saved,
  onClose,
}: {
  catalogPath: string;
  saved: SavedEvent | null;
  onClose: () => void;
}) {
  const [state, setState] = useState<SavedEvent>(
    saved && saved.catalogPath === catalogPath
      ? saved
      : { catalogPath, folderKeys: [], anchorsJob: null, completeJob: null, undoJob: null },
  );
  const [folders, setFolders] = useState<EventFolder[] | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [jobsById, setJobs] = useState<Record<string, EventJob>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const update = useCallback((next: SavedEvent) => {
    setState(next);
    store(next);
  }, []);

  const polling = useRef(new Set<string>());

  // One polling loop per job at a time; returns the job once it is no longer active.
  const follow = useCallback(async (jobId: string): Promise<EventJob | null> => {
    if (polling.current.has(jobId)) return null;
    polling.current.add(jobId);
    try {
      for (;;) {
        const job = await getEventJob(jobId);
        if (!alive.current) return job;
        setJobs((all) => ({ ...all, [jobId]: job }));
        if (!isActive(job.status)) return job;
        await new Promise((resolve) => window.setTimeout(resolve, POLL_MS));
      }
    } finally {
      polling.current.delete(jobId);
    }
  }, []);

  useEffect(() => {
    for (const id of [state.anchorsJob, state.completeJob, state.undoJob]) {
      if (id && !jobsById[id]) void follow(id).catch(() => undefined);
    }
  }, [state, jobsById, follow]);

  useEffect(() => {
    if (state.folderKeys.length || folders) return;
    listCatalogFolders(catalogPath)
      .then((result) => alive.current && setFolders(result.folders))
      .catch((cause) => setError(cause instanceof Error ? cause.message : "לא ניתן לקרוא את הקטלוג."));
  }, [catalogPath, state.folderKeys.length, folders]);

  async function act(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "הפעולה נכשלה.");
    } finally {
      setBusy(false);
    }
  }

  const startPlan = (slot: Slot, plan: () => Promise<EventJob>) =>
    act(async () => {
      const job = await plan();
      const next = { ...state, [slot]: job.job_id, ...(slot !== "undoJob" ? { undoJob: null } : {}) };
      update(next);
      await follow(job.job_id);
    });

  const confirm = (job: EventJob) =>
    act(async () => {
      await confirmEventJob(job.job_id);
      const done = await follow(job.job_id);
      if (done?.kind === "undo" && done.status === "completed" && done.parent_job) await follow(done.parent_job);
    });

  const cancel = (slot: Slot, job: EventJob) =>
    act(async () => {
      await cancelEventJob(job.job_id);
      update({ ...state, [slot]: null });
    });

  function close() {
    store(null);
    onClose();
  }

  const anchors = state.anchorsJob ? jobsById[state.anchorsJob] : null;
  const complete = state.completeJob ? jobsById[state.completeJob] : null;
  const undo = state.undoJob ? jobsById[state.undoJob] : null;
  const anchorsDone = anchors?.status === "completed";
  const chosenFolders = (folders ?? []).filter((f) => state.folderKeys.includes(f.key));

  function planButtons(slot: Slot, job: EventJob, confirmLabel: string) {
    return (
      <div className={styles.actions}>
        {canConfirm(job) ? (
          <button type="button" className={styles.primary} onClick={() => void confirm(job)} disabled={busy}>
            {confirmLabel}
          </button>
        ) : null}
        <button type="button" className={styles.secondary} onClick={() => void cancel(slot, job)} disabled={busy}>
          בטל
        </button>
      </div>
    );
  }

  function progress(job: EventJob) {
    return (
      <span className={styles.status}>
        {statusText(job.status)}
        {job.progress.total ? ` ${n(job.progress.done)} / ${n(job.progress.total)}` : ""}
      </span>
    );
  }

  function failure(job: EventJob, retry: "anchors" | "complete") {
    if (!canRetry(job)) {
      return (
        <span className={styles.warn}>
          {statusText(job.status)} {job.error ?? ""} אל תכתוב שוב לפני שתבדוק את הקטלוג מול הגיבוי בתיקייה
          &quot;ProGrapher Backups&quot; שליד הקטלוג.
        </span>
      );
    }
    return (
      <>
        <span className={styles.warn}>
          {statusText(job.status)} {job.error ?? ""}
        </span>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.secondary}
            onClick={retry === "anchors" ? plannedAnchors : plannedComplete}
            disabled={busy}
          >
            בדוק שוב
          </button>
        </div>
      </>
    );
  }

  const plannedAnchors = () => void startPlan("anchorsJob", () => planAnchors(catalogPath, state.folderKeys));
  const plannedComplete = () => void startPlan("completeJob", () => planCompletion(catalogPath, state.folderKeys));

  return (
    <section className={styles.panel} aria-label="אירוע מ-Lightroom">
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>אירוע מקטלוג Lightroom</span>
          <h3 title={catalogPath}>{fileName(catalogPath)}</h3>
        </div>
        <button type="button" className={styles.close} onClick={close} disabled={busy}>
          סגור
        </button>
      </header>

      <p className={styles.note}>
        בכל שלב Lightroom צריך להיות סגור. כל שינוי מתחיל בבדיקה שלא כותבת דבר, ונכתב רק אחרי שתאשר. לפני כל
        כתיבה נשמר גיבוי.
      </p>

      {!state.folderKeys.length ? (
        <div className={styles.scope}>
          <strong>אילו תיקיות שייכות לאירוע הזה?</strong>
          <span>ProGrapher יעבוד רק על התמונות בתיקיות שתבחר. שאר הקטלוג לא ייקרא ולא ישתנה.</span>
          {folders === null ? (
            <span className={styles.status}>קורא את רשימת התיקיות…</span>
          ) : (
            <ul className={styles.folderList}>
              {folders.map((folder) => (
                <li key={folder.key}>
                  <label>
                    <input
                      type="checkbox"
                      checked={chosen.includes(folder.key)}
                      onChange={(event) =>
                        setChosen((keys) =>
                          event.target.checked ? [...keys, folder.key] : keys.filter((k) => k !== folder.key),
                        )
                      }
                    />
                    <bdi dir="ltr">{folder.label}</bdi>
                    <span>
                      {n(folder.photos)} תמונות · {folder.first}
                      {folder.last !== folder.first ? ` – ${folder.last}` : ""}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.primary}
              disabled={!chosen.length}
              onClick={() => update({ ...state, folderKeys: chosen })}
            >
              המשך עם {chosen.length} תיקיות
            </button>
          </div>
        </div>
      ) : (
        <ol className={styles.steps}>
          <li className={anchorsDone ? styles.done : styles.current}>
            <div className={styles.body}>
              <strong>1. בחירת תמונות לעריכה</strong>
              {!anchors ? (
                <span>ProGrapher מחלק את האירוע לרגעים ובוחר תמונה אחת מכל רגע מרכזי. קודם תראה מה ייעשה.</span>
              ) : isActive(anchors.status) ? (
                progress(anchors)
              ) : anchors.status === "planned" ? (
                <>
                  <span>
                    יסומנו {n(anchors.plan?.anchor_count)} תמונות מתוך {n(anchors.plan?.photos)} ({n(anchors.plan?.moments)}{" "}
                    רגעים) ב-Collection &quot;{String(anchors.plan?.collection_name ?? "")}&quot;. תווית סגולה תתווסף ל-
                    {n(anchors.plan?.to_label)} מהן; תוויות שכבר שמת לא ישתנו. גיבוי יישמר ב-
                    <bdi dir="ltr">{String(anchors.plan?.backup_folder ?? "")}</bdi>.
                  </span>
                  {planButtons("anchorsJob", anchors, "אשר וסמן ב-Lightroom")}
                </>
              ) : anchors.status === "completed" ? (
                <span>
                  סומנו {n(anchors.result?.marked)} תמונות ב-Collection &quot;{String(anchors.result?.collection_name ?? "")}
                  &quot;.
                </span>
              ) : (
                failure(anchors, "anchors")
              )}
            </div>
            {!anchors || anchors.status === "completed" || anchors.status === "cancelled" ? (
              <div className={styles.actions}>
                <button
                  type="button"
                  className={anchors ? styles.secondary : styles.primary}
                  onClick={plannedAnchors}
                  disabled={busy}
                >
                  {anchors ? "בחר מחדש" : "בדוק אילו תמונות לסמן"}
                </button>
                {anchorsDone && !complete ? (
                  <button
                    type="button"
                    className={styles.undo}
                    onClick={() => void startPlan("undoJob", () => planUndo(anchors.job_id))}
                    disabled={busy}
                  >
                    בטל סימון
                  </button>
                ) : null}
              </div>
            ) : null}
          </li>

          <li className={!anchorsDone ? styles.waiting : complete?.status === "completed" ? styles.done : styles.current}>
            <div className={styles.body}>
              <strong>2. עריכה ב-Lightroom</strong>
              <span>
                פתח את הקטלוג ב-Lightroom, ערוך את התמונות ב-Collection שסומן כמו שאתה עורך תמיד, וסגור את Lightroom.
              </span>
            </div>
          </li>

          <li className={!anchorsDone ? styles.waiting : complete?.status === "completed" ? styles.done : styles.current}>
            <div className={styles.body}>
              <strong>3. השלמת האירוע</strong>
              {!complete ? (
                <span>קודם בדיקה: מה ייכתב, מה ידולג ולמה. שום דבר לא נכתב עד שתאשר.</span>
              ) : isActive(complete.status) ? (
                progress(complete)
              ) : complete.status === "planned" ? (
                <CompletionSummary job={complete} />
              ) : complete.status === "completed" || complete.status === "undone" || complete.status === "partially_undone" ? (
                <span>
                  נכתבו {n(complete.result?.written)} תמונות, ובכל אחת מופיע ב-History שלב &quot;ProGrapher&quot;.{" "}
                  {complete.status !== "completed" ? statusText(complete.status) : ""}
                </span>
              ) : (
                failure(complete, "complete")
              )}
              {complete?.status === "planned" ? planButtons("completeJob", complete, "אשר וכתוב לקטלוג") : null}
            </div>
            {anchorsDone && (!complete || ["completed", "cancelled", "undone", "partially_undone"].includes(complete.status)) ? (
              <div className={styles.actions}>
                <button type="button" className={complete ? styles.secondary : styles.primary} onClick={plannedComplete} disabled={busy}>
                  {complete ? "בדוק שוב" : "בדוק לפני השלמה"}
                </button>
                {complete?.status === "completed" ? (
                  <button
                    type="button"
                    className={styles.undo}
                    onClick={() => void startPlan("undoJob", () => planUndo(complete.job_id))}
                    disabled={busy}
                  >
                    בדוק ביטול
                  </button>
                ) : null}
              </div>
            ) : null}
          </li>
        </ol>
      )}

      {undo ? (
        <div className={styles.undoBox}>
          <strong>ביטול</strong>
          {isActive(undo.status) ? (
            progress(undo)
          ) : undo.status === "planned" ? (
            <>
              {undo.plan?.kind === "unmark" ? (
                <span>
                  {undo.plan?.collection_removable
                    ? `ה-Collection "${String(undo.plan?.collection_name ?? "")}" יימחק`
                    : "ה-Collection השתנה מאז ש-ProGrapher יצר אותו ולכן יישאר"}
                  , ויוסרו {n(undo.plan?.labels_to_clear)} תוויות סגולות ש-ProGrapher הוסיף.
                </span>
              ) : (
                <span>
                  יוחזרו {n(undo.plan?.will_revert)} תמונות למצב שלפני ProGrapher.
                  {skipLines(undo.plan?.kept as Record<string, number> | undefined).map((line) => ` ${line} – יישארו כמו שהן.`)}
                </span>
              )}
              {planButtons("undoJob", undo, "אשר ביטול")}
            </>
          ) : undo.status === "completed" ? (
            <span>
              {undo.result?.reverted !== undefined
                ? `הוחזרו ${n(undo.result?.reverted)} תמונות; ${n(undo.result?.kept)} נשארו כי ערכת אותן אחרי ProGrapher.`
                : "הסימון בוטל."}
            </span>
          ) : (
            <span className={styles.warn}>
              {statusText(undo.status)} {undo.error ?? ""}
            </span>
          )}
        </div>
      ) : null}

      {chosenFolders.length ? (
        <p className={styles.note}>
          האירוע: {chosenFolders.map((f) => f.label).join(", ")}
        </p>
      ) : null}
      {error ? <div className={styles.error}>{error}</div> : null}
    </section>
  );
}

function CompletionSummary({ job }: { job: EventJob }) {
  const plan = job.plan ?? {};
  const assessment = (plan.assessment ?? {}) as Record<string, unknown>;
  const blocking = (plan.blocking ?? []) as { reason: string; edited?: number; required?: number }[];
  const lightGaps = (assessment.light_bins_without_example ?? []) as string[];
  return (
    <ul className={styles.summary}>
      <li>
        ייכתבו: <b>{n(plan.will_write)}</b> תמונות
        {Array.isArray(plan.sliders) && plan.sliders.length ? ` (${sliderList(plan.sliders as string[])})` : ""}
      </li>
      {skipLines(plan.skipped as Record<string, number> | undefined).map((line) => (
        <li key={line}>ידולגו – {line}</li>
      ))}
      <li>
        תמונות שערכת: {n(assessment.anchors_edited)} (נדרשות לפחות {n(assessment.required_edited)}). רגעים עם תמונה
        ערוכה: {n(assessment.moments_with_edited_anchor)} מתוך {n(assessment.moments)}, כלומר{" "}
        {percent(Number(assessment.covered_share ?? 0))} מתמונות האירוע.
      </li>
      {lightGaps.length ? (
        <li className={styles.warn}>אין תמונה ערוכה בתנאי אור: {lightGaps.join(", ")}. התמונות שם ידולגו.</li>
      ) : null}
      <li>
        גיבוי יישמר ב-<bdi dir="ltr">{String(plan.backup_folder ?? "")}</bdi>
      </li>
      {blocking.map((block) => (
        <li key={block.reason} className={styles.warn}>
          {blockingText(block)}
        </li>
      ))}
    </ul>
  );
}
