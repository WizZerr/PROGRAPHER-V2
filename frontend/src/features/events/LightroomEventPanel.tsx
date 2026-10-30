"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { listLearningProfiles, type LearningProfile } from "@/features/learning-intake/learningIntake.api";
import {
  cancelEventJob,
  confirmEventJob,
  getEventJob,
  listCatalogFolders,
  planAutomatic,
  planUndo,
} from "./eventEdit.api";
import {
  blockingText,
  canConfirm,
  canRetry,
  exposureText,
  isActive,
  matchingText,
  parseSaved,
  progressText,
  requiredAcknowledgements,
  skipLines,
  sliderList,
  statusText,
  uniformExposureWarning,
  type EventFolder,
  type EventJob,
  type SavedEvent,
} from "./eventFlow";
import styles from "./LightroomEventPanel.module.css";

const STORAGE_KEY = "pg.lightroomEvent.v3";
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

type Slot = "completeJob" | "undoJob";

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
      : { catalogPath, folderKeys: [], profileId: null, completeJob: null, undoJob: null },
  );
  const [folders, setFolders] = useState<EventFolder[] | null>(null);
  const [profiles, setProfiles] = useState<LearningProfile[] | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [jobsById, setJobs] = useState<Record<string, EventJob>>({});
  const [busy, setBusy] = useState(false);
  // Dedicated confirmations given for one plan (job id), e.g. "uniform_exposure"; a new plan starts with none.
  const [acknowledged, setAcknowledged] = useState<{ job: string; given: string[] }>({ job: "", given: [] });
  const [error, setError] = useState("");
  const alive = useRef(true);
  const polling = useRef(new Set<string>());

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
    for (const id of [state.completeJob, state.undoJob]) {
      if (id && !jobsById[id]) void follow(id).catch(() => undefined);
    }
  }, [state, jobsById, follow]);

  useEffect(() => {
    if (state.folderKeys.length || folders) return;
    listCatalogFolders(catalogPath)
      .then((result) => alive.current && setFolders(result.folders))
      .catch((cause) => setError(cause instanceof Error ? cause.message : "לא ניתן לקרוא את הקטלוג."));
  }, [catalogPath, state.folderKeys.length, folders]);

  useEffect(() => {
    if (profiles) return;
    listLearningProfiles()
      .then((items) => {
        if (!alive.current) return;
        setProfiles(items);
        if (items.length === 1 && !state.profileId) update({ ...state, profileId: items[0].profile_id });
      })
      .catch(() => setProfiles([]));
  }, [profiles, state, update]);

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
      update({ ...state, [slot]: job.job_id, ...(slot === "completeJob" ? { undoJob: null } : {}) });
      await follow(job.job_id);
    });

  const confirm = (job: EventJob) =>
    act(async () => {
      await confirmEventJob(job.job_id, acknowledgedFor(job));
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

  const complete = state.completeJob ? jobsById[state.completeJob] : null;
  const undo = state.undoJob ? jobsById[state.undoJob] : null;
  const profile = (profiles ?? []).find((p) => p.profile_id === state.profileId) ?? null;
  const planEvent = () =>
    state.profileId &&
    void startPlan("completeJob", () => planAutomatic(catalogPath, state.folderKeys, state.profileId as string));

  function acknowledgedFor(job: EventJob): string[] {
    return acknowledged.job === job.job_id ? acknowledged.given : [];
  }

  function toggleAcknowledgement(job: EventJob, name: string, on: boolean) {
    const given = acknowledgedFor(job).filter((a) => a !== name);
    setAcknowledged({ job: job.job_id, given: on ? [...given, name] : given });
  }

  function planButtons(slot: Slot, job: EventJob, confirmLabel: string) {
    const needed = requiredAcknowledgements(job);
    return (
      <div className={styles.actions}>
        {needed.includes("uniform_exposure") && !job.plan?.blocking?.length ? (
          <label className={styles.warn}>
            <input
              type="checkbox"
              checked={acknowledgedFor(job).includes("uniform_exposure")}
              onChange={(e) => toggleAcknowledgement(job, "uniform_exposure", e.target.checked)}
              disabled={busy}
            />{" "}
            {uniformExposureWarning((job.plan?.exposure ?? {}) as Record<string, never>)} <b>מאשר/ת לכתוב בכל זאת.</b>
          </label>
        ) : null}
        {job.status === "planned" && !job.plan?.blocking?.length ? (
          <button
            type="button"
            className={styles.primary}
            onClick={() => void confirm(job)}
            disabled={busy || !canConfirm(job, acknowledgedFor(job))}
          >
            {confirmLabel}
          </button>
        ) : null}
        <button type="button" className={styles.secondary} onClick={() => void cancel(slot, job)} disabled={busy}>
          בטל
        </button>
      </div>
    );
  }

  function failure(job: EventJob) {
    if (!canRetry(job)) {
      return (
        <span className={styles.warn}>
          {statusText(job.status)} {job.error ?? ""} אל תכתוב שוב לפני שתבדוק את הקטלוג מול הגיבוי בתיקייה
          &quot;ProGrapher Backups&quot; שליד הקטלוג.
        </span>
      );
    }
    return (
      <span className={styles.warn}>
        {statusText(job.status)} {job.error ?? ""}
      </span>
    );
  }

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
        ProGrapher עורך את כל האירוע לפי הסגנון שלמד בפרופיל. Lightroom צריך להיות סגור. קודם תראה מה ייכתב, ושום
        דבר לא נכתב עד שתאשר. לפני הכתיבה נשמר גיבוי.
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
          <li className={complete?.status === "completed" ? styles.done : styles.current}>
            <div className={styles.body}>
              <strong>עריכה אוטומטית של האירוע</strong>
              {profiles && profiles.length > 1 && !complete ? (
                <label className={styles.profilePick}>
                  לפי הפרופיל:
                  <select
                    value={state.profileId ?? ""}
                    onChange={(event) => update({ ...state, profileId: event.target.value || null })}
                  >
                    <option value="">בחר פרופיל…</option>
                    {profiles.map((p) => (
                      <option key={p.profile_id} value={p.profile_id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : profile ? (
                <span>לפי הפרופיל &quot;{profile.name}&quot;.</span>
              ) : profiles && !profiles.length ? (
                <span className={styles.warn}>אין עדיין פרופיל למידה. צור פרופיל ב&quot;הפרופיל שלי&quot; קודם.</span>
              ) : null}
              {!complete ? null : isActive(complete.status) ? (
                <span className={styles.status}>{progressText(complete)}</span>
              ) : complete.status === "planned" ? (
                <AutomaticSummary job={complete} />
              ) : ["completed", "undone", "partially_undone"].includes(complete.status) ? (
                <span>
                  נכתבו {n(complete.result?.written)} תמונות, ובכל אחת מופיע ב-History שלב &quot;ProGrapher&quot;. פתח את
                  הקטלוג ב-Lightroom כדי לראות.{" "}
                  {complete.status !== "completed" ? statusText(complete.status) : ""}
                </span>
              ) : (
                failure(complete)
              )}
              {complete?.status === "planned" ? planButtons("completeJob", complete, "אשר וכתוב לקטלוג") : null}
            </div>
            {!complete || !(isActive(complete.status) || complete.status === "planned") ? (
              <div className={styles.actions}>
                <button
                  type="button"
                  className={complete ? styles.secondary : styles.primary}
                  onClick={planEvent}
                  disabled={busy || !state.profileId || (!!complete && !canRetry(complete) && complete.status === "failed")}
                >
                  {complete ? "בדוק שוב" : "בדוק עריכה אוטומטית"}
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
            <span className={styles.status}>{progressText(undo)}</span>
          ) : undo.status === "planned" ? (
            <>
              <span>
                יוחזרו {n(undo.plan?.will_revert)} תמונות למצב שלפני ProGrapher.
                {skipLines(undo.plan?.kept as Record<string, number> | undefined).map((line) => ` ${line} – יישארו כמו שהן.`)}
              </span>
              {planButtons("undoJob", undo, "אשר ביטול")}
            </>
          ) : undo.status === "completed" ? (
            <span>
              הוחזרו {n(undo.result?.reverted)} תמונות; {n(undo.result?.kept)} נשארו כי ערכת אותן אחרי ProGrapher.
            </span>
          ) : (
            <span className={styles.warn}>
              {statusText(undo.status)} {undo.error ?? ""}
            </span>
          )}
        </div>
      ) : null}

      {error ? <div className={styles.error}>{error}</div> : null}
    </section>
  );
}

function AutomaticSummary({ job }: { job: EventJob }) {
  const plan = job.plan ?? {};
  const style = (plan.style ?? {}) as Record<string, unknown>;
  const blocking = (plan.blocking ?? []) as { reason: string }[];
  return (
    <ul className={styles.summary}>
      <li>
        ייכתבו: <b>{n(plan.will_write)}</b> מתוך {n(plan.photos)} תמונות
        {Array.isArray(plan.sliders) && plan.sliders.length ? ` (${sliderList(plan.sliders as string[])})` : ""}
      </li>
      {skipLines(plan.skipped as Record<string, number> | undefined).map((line) => (
        <li key={line}>לא ישתנו – {line}</li>
      ))}
      <li>{exposureText((plan.exposure ?? {}) as Record<string, never>)}</li>
      {matchingText((plan.exposure ?? {}) as Record<string, never>) ? (
        <li>{matchingText((plan.exposure ?? {}) as Record<string, never>)}</li>
      ) : null}
      <li>איזון לבן: נשאר As Shot, כמו שהמצלמה צילמה.</li>
      <li>הסגנון נלמד מ-{n(style.photos)} תמונות ערוכות בפרופיל.</li>
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
