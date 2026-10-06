"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useAccountIdentity } from "@/features/account/AccountIdentity";
import {
  getTestingProfile,
  type LearningSource,
  type TestingProfile,
} from "@/features/testing/testing.api";
import { useWorkspaceNav } from "@/features/workspace/workspace-nav";
import {
  getPhotographerSetup,
  saveStylePreferences,
  selectEditsFolder,
  selectLightroomCatalog,
  type PhotographerSetupOverview,
  type PhotographerSetupStatus,
} from "./profile.api";
import styles from "./ProfileScreen.module.css";

const STATUS_LABELS: Record<PhotographerSetupStatus, string> = {
  no_profile: "עדיין לא הוגדר",
  data_review: "בודק את החומר",
  training: "באימון",
  needs_more_data: "צריך עוד חומר",
  experimental: "פרופיל ניסויי",
  evaluated: "מוכן לעבודה",
};

type ActivityItem = {
  title: string;
  meta: string;
  date: string | null;
};

function formatDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("he-IL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

function LearningState({
  label,
  ready,
}: {
  label: string;
  ready: boolean;
}) {
  return (
    <span className={ready ? styles.stateReady : styles.stateIdle}>
      <span aria-hidden="true" />
      {label}
    </span>
  );
}

export default function ProfileScreen() {
  const openView = useWorkspaceNav();
  const {
    identity,
    firstNameLabel,
    profileOwnerLabel,
    updateIdentity,
  } = useAccountIdentity();

  const [overview, setOverview] =
    useState<PhotographerSetupOverview | null>(null);
  const [jpegProfile, setJpegProfile] = useState<TestingProfile | null>(null);
  const [rawProfile, setRawProfile] = useState<TestingProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);

  const [firstNameDraft, setFirstNameDraft] = useState("");
  const [profileNameDraft, setProfileNameDraft] = useState("");
  const [styleName, setStyleName] = useState("");
  const [presetPath, setPresetPath] = useState<string | null>(null);
  const [profileMode, setProfileMode] =
    useState<"from_source" | "explicit">("from_source");
  const [cameraProfile, setCameraProfile] = useState("");

  const applyOverview = useCallback((value: PhotographerSetupOverview) => {
    setOverview(value);
    setStyleName(value.setup.style_name ?? "");
    setPresetPath(value.setup.preset_path);
    setProfileMode(value.setup.color_profile_mode);
    setCameraProfile(value.setup.camera_profile ?? "");
  }, []);

  const refresh = useCallback(async () => {
    setError("");
    try {
      const [setup, jpeg, raw] = await Promise.all([
        getPhotographerSetup(),
        getTestingProfile("jpeg").catch(() => null),
        getTestingProfile("raw").catch(() => null),
      ]);
      applyOverview(setup);
      setJpegProfile(jpeg);
      setRawProfile(raw);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "לא ניתן לטעון את הפרופיל.",
      );
    }
  }, [applyOverview]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    setFirstNameDraft(identity.firstName);
    setProfileNameDraft(identity.profileName ?? "");
  }, [identity]);

  function openLearning(source: LearningSource) {
    try {
      window.sessionStorage.setItem("prographer.training.preferred-source", source);
    } catch {
      // Navigation still works even if session storage is unavailable.
    }
    openView("training");
  }

  async function chooseCatalog() {
    setError("");
    setSaved("");

    const selected = await open({
      multiple: false,
      directory: false,
      title: "בחר קטלוג Lightroom",
      filters: [{ name: "Lightroom Catalog", extensions: ["lrcat"] }],
    });
    if (!selected || Array.isArray(selected)) return;

    setBusy(true);
    try {
      applyOverview(await selectLightroomCatalog(selected));
      setSaved("קטלוג Lightroom נשמר בפרופיל.");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן לקרוא את קטלוג Lightroom.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function chooseEditsFolder() {
    setError("");
    setSaved("");

    const selected = await open({
      multiple: false,
      directory: true,
      title: "בחר תיקיית עריכות / XMP",
    });
    if (!selected || Array.isArray(selected)) return;

    setBusy(true);
    try {
      applyOverview(await selectEditsFolder(selected));
      setSaved("תיקיית העריכות נשמרה בפרופיל.");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן לקרוא את תיקיית העריכות.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function choosePreset() {
    setError("");
    setSaved("");

    const selected = await open({
      multiple: false,
      directory: false,
      title: "בחר פריסט Lightroom",
      filters: [{ name: "Lightroom Preset", extensions: ["xmp"] }],
    });
    if (!selected || Array.isArray(selected)) return;
    setPresetPath(selected);
  }

  async function saveSettings() {
    setBusy(true);
    setError("");
    setSaved("");

    try {
      const nextFirstName = firstNameDraft.trim();
      const nextProfileName = profileNameDraft.trim();

      updateIdentity({
        firstName: nextFirstName,
        displayName: nextFirstName,
        profileName: nextProfileName || null,
      });

      const result = await saveStylePreferences({
        style_name: styleName.trim() || null,
        preset_path: presetPath,
        color_profile_mode: profileMode,
        camera_profile:
          profileMode === "explicit" ? cameraProfile.trim() || null : null,
      });

      applyOverview(result);
      setSaved("הפרופיל עודכן.");
      setSettingsOpen(false);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "לא ניתן לשמור את הפרופיל.",
      );
    } finally {
      setBusy(false);
    }
  }

  const setup = overview?.setup;
  const profileReady = setup?.status === "evaluated";
  const jpegReady = Boolean(jpegProfile && jpegProfile.usable_pairs > 0);
  const rawReady = Boolean(rawProfile && rawProfile.usable_pairs > 0);
  const catalogReady = Boolean(
    overview?.selected_catalog?.readable && overview.selected_catalog.sqlite_valid,
  );
  const hasAnyMaterial = jpegReady || rawReady || catalogReady;

  const overallStatus = profileReady
    ? STATUS_LABELS.evaluated
    : hasAnyMaterial
      ? "בתהליך בנייה"
      : setup
        ? STATUS_LABELS[setup.status]
        : "טוען…";

  const activity = useMemo<ActivityItem[]>(() => {
    const items: ActivityItem[] = [];

    if (jpegProfile) {
      items.push({
        title: "חומר JPEG נבדק",
        meta: `${jpegProfile.usable_pairs.toLocaleString("he-IL")} זוגות שמישים`,
        date: jpegProfile.created_at,
      });
    }

    if (overview?.selected_catalog) {
      const count = overview.selected_catalog.catalog_photo_records;
      items.push({
        title: "קטלוג Lightroom נבחר",
        meta:
          typeof count === "number"
            ? `${count.toLocaleString("he-IL")} רשומות צילום`
            : "הקטלוג מוכן לניתוח",
        date: overview.setup.updated_at,
      });
    }

    if (rawProfile) {
      items.push({
        title: "חומר RAW נבדק",
        meta: `${rawProfile.usable_pairs.toLocaleString("he-IL")} זוגות שמישים`,
        date: rawProfile.created_at,
      });
    }

    return items.slice(0, 3);
  }, [jpegProfile, rawProfile, overview]);

  return (
    <section className={styles.screen}>
      <header className={styles.profileHeader}>
        <div className={styles.profileIdentity}>
          <span className={styles.eyebrow}>הפרופיל שלי</span>
          <h1>סגנון העריכה של {profileOwnerLabel}</h1>
          <p>
            כל מסלול לומד בנפרד את דרך העריכה שלך. כאן רואים מה כבר מוכן,
            מה חסר ומה הפעולה הבאה.
          </p>
        </div>

        <div className={styles.headerControls}>
          <div className={styles.profileStatus}>
            <span
              className={profileReady ? styles.readyDot : styles.pendingDot}
              aria-hidden="true"
            />
            <div>
              <small>מצב הפרופיל</small>
              <strong>{overallStatus}</strong>
            </div>
          </div>

          <button
            className={styles.settingsButton}
            type="button"
            aria-label="הגדרות הפרופיל"
            title="הגדרות הפרופיל"
            onClick={() => setSettingsOpen(true)}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="3.2" />
              <path d="M19 13.6v-3.2l-2.1-.6a7.3 7.3 0 0 0-.7-1.6l1-1.9-2.3-2.3-1.9 1a7.3 7.3 0 0 0-1.6-.7L10.8 2H7.6L7 4.2a7.3 7.3 0 0 0-1.6.7l-1.9-1-2.3 2.3 1 1.9a7.3 7.3 0 0 0-.7 1.6l-2.1.6v3.2l2.1.6c.2.6.4 1.1.7 1.6l-1 1.9 2.3 2.3 1.9-1c.5.3 1 .5 1.6.7l.6 2.1h3.2l.6-2.1c.6-.2 1.1-.4 1.6-.7l1.9 1 2.3-2.3-1-1.9c.3-.5.5-1 .7-1.6l2.1-.6Z" />
            </svg>
          </button>
        </div>
      </header>

      {error ? <div className={styles.error}>{error}</div> : null}
      {saved ? <div className={styles.success}>{saved}</div> : null}

      <section className={styles.learningSection}>
        <div className={styles.sectionHeader}>
          <div>
            <span className={styles.sectionLabel}>מסלולי JPEG</span>
            <h2>שתי דרכים ללמוד את העריכה שלך</h2>
          </div>
          <p>כל מסלול נשמר, נמדד ומתפתח בנפרד.</p>
        </div>

        <div className={styles.primaryTracks}>
          <article className={styles.learningCard}>
            <div className={styles.cardTop}>
              <span className={styles.formatBadge}>JPEG</span>
              <LearningState
                ready={jpegReady}
                label={jpegReady ? "חומר מוכן" : "לא הוגדר"}
              />
            </div>

            <div className={styles.cardCopy}>
              <h3>לפני + אחרי</h3>
              <p>
                תמונות JPEG מקור מול הגרסה הסופית שכבר ערכת. ProGrapher לומד
                מההבדל ביניהן.
              </p>
            </div>

            {jpegProfile ? (
              <div className={styles.cardMetrics}>
                <div>
                  <span>זוגות שמישים</span>
                  <strong>{jpegProfile.usable_pairs.toLocaleString("he-IL")}</strong>
                </div>
                <div>
                  <span>קובצי מקור</span>
                  <strong>{jpegProfile.raw_files.toLocaleString("he-IL")}</strong>
                </div>
              </div>
            ) : (
              <div className={styles.emptyHint}>
                צריך שתי תיקיות: JPEG מקור ו-JPEG ערוך.
              </div>
            )}

            <button
              className={styles.cardAction}
              type="button"
              onClick={() => openLearning("jpeg")}
            >
              {jpegProfile ? "המשך למסלול" : "התחל הגדרה"}
              <span aria-hidden="true">←</span>
            </button>
          </article>

          <article className={styles.learningCard}>
            <div className={styles.cardTop}>
              <span className={styles.formatBadge}>JPEG + LR</span>
              <LearningState
                ready={catalogReady}
                label={catalogReady ? "קטלוג נבחר" : "לא הוגדר"}
              />
            </div>

            <div className={styles.cardCopy}>
              <h3>Lightroom Catalog</h3>
              <p>
                JPEG יחד עם החלטות העריכה שנשמרו ב-Lightroom. זהו מסלול למידה
                נפרד ממסלול לפני/אחרי.
              </p>
            </div>

            {overview?.selected_catalog ? (
              <div className={styles.catalogInfo}>
                <span>קטלוג נבחר</span>
                <strong>
                  {overview.selected_catalog.catalog_photo_records !== null
                    ? `${overview.selected_catalog.catalog_photo_records.toLocaleString("he-IL")} רשומות`
                    : "מוכן לניתוח"}
                </strong>
                <small>
                  מנוע הלמידה למסלול הזה יחובר בנפרד עם חומר הצלם.
                </small>
              </div>
            ) : (
              <div className={styles.emptyHint}>
                בחר קובץ Lightroom Catalog כדי להכין את המסלול.
              </div>
            )}

            <button
              className={styles.cardAction}
              type="button"
              onClick={() => void chooseCatalog()}
              disabled={busy}
            >
              {overview?.selected_catalog ? "החלף קטלוג" : "בחר קטלוג Lightroom"}
              <span aria-hidden="true">←</span>
            </button>
          </article>
        </div>
      </section>

      <section className={styles.rawLane}>
        <div className={styles.rawIdentity}>
          <span className={styles.rawBadge}>RAW</span>
          <div>
            <strong>RAW + Lightroom/XMP</strong>
            <small>
              מסלול משני כרגע. נוכל להפעיל אותו אם נקבל מהצלם חומר RAW מתאים.
            </small>
          </div>
        </div>

        <div className={styles.rawControls}>
          <LearningState
            ready={rawReady}
            label={rawReady ? "חומר מוכן" : "לא הוגדר"}
          />
          <button type="button" onClick={() => openLearning("raw")}>
            {rawProfile ? "המשך" : "הגדר RAW"}
          </button>
        </div>
      </section>

      <section className={styles.activitySection}>
        <div className={styles.sectionHeader}>
          <div>
            <span className={styles.sectionLabel}>פעילות אחרונה</span>
            <h2>מה קרה בפרופיל</h2>
          </div>
        </div>

        {activity.length === 0 ? (
          <div className={styles.activityEmpty}>
            <span aria-hidden="true">○</span>
            <div>
              <strong>אין עדיין פעילות בפרופיל</strong>
              <small>
                אחרי שתוסיף חומר, בדיקות והתקדמות יופיעו כאן בצורה פשוטה.
              </small>
            </div>
          </div>
        ) : (
          <div className={styles.activityList}>
            {activity.map((item) => (
              <div className={styles.activityRow} key={`${item.title}-${item.date ?? ""}`}>
                <span className={styles.activityDot} aria-hidden="true" />
                <div>
                  <strong>{item.title}</strong>
                  <small>{item.meta}</small>
                </div>
                <time>{formatDate(item.date)}</time>
              </div>
            ))}
          </div>
        )}
      </section>

      {settingsOpen ? (
        <div
          className={styles.modalBackdrop}
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) setSettingsOpen(false);
          }}
        >
          <section
            className={styles.settingsModal}
            role="dialog"
            aria-modal="true"
            aria-label="הגדרות הפרופיל"
          >
            <header className={styles.modalHeader}>
              <div>
                <span className={styles.sectionLabel}>הגדרות פרופיל</span>
                <h2>החשבון והסגנון שלך</h2>
              </div>
              <button
                type="button"
                aria-label="סגור"
                onClick={() => setSettingsOpen(false)}
              >
                ×
              </button>
            </header>

            <div className={styles.settingsScroll}>
              <section className={styles.settingsGroup}>
                <div className={styles.settingsGroupHead}>
                  <div>
                    <strong>זהות החשבון</strong>
                    <small>
                      נשמר מקומית כרגע ויתחבר לאותו contract כשנוסיף Accounts.
                    </small>
                  </div>
                </div>

                <div className={styles.formGrid}>
                  <label>
                    <span>שם פרטי</span>
                    <input
                      value={firstNameDraft}
                      onChange={(event) => setFirstNameDraft(event.target.value)}
                      placeholder="לדוגמה: מתן"
                    />
                  </label>

                  <label>
                    <span>שם הפרופיל</span>
                    <input
                      value={profileNameDraft}
                      onChange={(event) => setProfileNameDraft(event.target.value)}
                      placeholder={`${firstNameLabel} Weddings`}
                    />
                    <small>
                      אם ריק, יוצג השם הפרטי: {firstNameLabel}
                    </small>
                  </label>
                </div>
              </section>

              <section className={styles.settingsGroup}>
                <div className={styles.settingsGroupHead}>
                  <div>
                    <strong>Lightroom</strong>
                    <small>
                      כל הפרטים הטכניים נשארים כאן, מחוץ למסך הראשי.
                    </small>
                  </div>
                  <span
                    className={
                      overview?.lightroom.detected
                        ? styles.lightroomReady
                        : styles.lightroomIdle
                    }
                  >
                    {overview?.lightroom.detected ? "זוהה" : "לא זוהה"}
                  </span>
                </div>

                <div className={styles.settingsActions}>
                  <button type="button" onClick={() => void chooseCatalog()} disabled={busy}>
                    {overview?.selected_catalog ? "החלף קטלוג" : "בחר קטלוג Lightroom"}
                  </button>
                  <button type="button" onClick={() => void chooseEditsFolder()} disabled={busy}>
                    {overview?.selected_edits_folder ? "החלף תיקיית XMP" : "בחר תיקיית עריכות / XMP"}
                  </button>
                </div>
              </section>

              <section className={styles.settingsGroup}>
                <div className={styles.settingsGroupHead}>
                  <div>
                    <strong>העדפות סגנון</strong>
                    <small>אופציונלי. חומר העריכה האמיתי הוא מקור הלמידה.</small>
                  </div>
                </div>

                <div className={styles.formGrid}>
                  <label>
                    <span>שם הסגנון</span>
                    <input
                      value={styleName}
                      onChange={(event) => setStyleName(event.target.value)}
                      placeholder="לדוגמה: טבעי וחם"
                    />
                  </label>

                  <div className={styles.fieldButton}>
                    <span>פריסט Lightroom</span>
                    <button
                      type="button"
                      onClick={() => void choosePreset()}
                      disabled={busy}
                    >
                      {presetPath ? "החלף פריסט" : "בחר פריסט"}
                    </button>
                  </div>
                </div>

                <div className={styles.profileModes}>
                  <label>
                    <input
                      type="radio"
                      name="profile-mode"
                      checked={profileMode === "from_source"}
                      onChange={() => setProfileMode("from_source")}
                    />
                    <span>קבע פרופיל צבע מתוך החומר</span>
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="profile-mode"
                      checked={profileMode === "explicit"}
                      onChange={() => setProfileMode("explicit")}
                    />
                    <span>הגדר פרופיל צבע ידנית</span>
                  </label>

                  {profileMode === "explicit" ? (
                    <input
                      value={cameraProfile}
                      onChange={(event) => setCameraProfile(event.target.value)}
                      placeholder="לדוגמה: Adobe Color"
                    />
                  ) : null}
                </div>
              </section>
            </div>

            <footer className={styles.modalFooter}>
              <span>
                שלום, {firstNameDraft.trim() || "צלם"} · סגנון העריכה של{" "}
                {profileNameDraft.trim() || firstNameDraft.trim() || "צלם"}
              </span>
              <div>
                <button
                  className={styles.cancelButton}
                  type="button"
                  onClick={() => setSettingsOpen(false)}
                >
                  ביטול
                </button>
                <button
                  className={styles.saveButton}
                  type="button"
                  onClick={() => void saveSettings()}
                  disabled={busy}
                >
                  {busy ? "שומר…" : "שמור"}
                </button>
              </div>
            </footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}
