"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useAccountIdentity } from "@/features/account/AccountIdentity";
import {
  getTestingProfile,
  type TestingProfile,
} from "@/features/testing/testing.api";
import {
  loadCatalogBindings,
  writeTrainingEntry,
  type CatalogBinding,
  type LearningMedia,
} from "@/features/training/learning-state";
import { useWorkspaceNav } from "@/features/workspace/workspace-nav";
import {
  getPhotographerSetup,
  saveStylePreferences,
  type PhotographerSetupOverview,
} from "./profile.api";
import styles from "./ProfileScreen.module.css";

type RouteState = "idle" | "pending" | "ready";

function routeState(profile: TestingProfile | null): RouteState {
  if (!profile) return "idle";
  return profile.usable_pairs > 0 ? "ready" : "pending";
}

function jpegPairStatus(profile: TestingProfile | null): string {
  if (!profile) return "לא הוגדר";
  if (profile.usable_pairs <= 0) return "נבדק · אין חומר שמיש";
  return `${profile.usable_pairs.toLocaleString("he-IL")} זוגות מוכנים`;
}

function catalogStatus(binding?: CatalogBinding): string {
  if (!binding) return "לא הוגדר";
  return binding.catalogPhotoRecords !== null
    ? `${binding.catalogPhotoRecords.toLocaleString("he-IL")} רשומות בקטלוג`
    : "קטלוג הוגדר";
}

function rawStatus(
  profile: TestingProfile | null,
  catalog?: CatalogBinding,
): { state: RouteState; label: string; source: string } {
  if (profile?.usable_pairs && profile.usable_pairs > 0) {
    return {
      state: "ready",
      label: `${profile.usable_pairs.toLocaleString("he-IL")} זוגות RAW/XMP`,
      source: "עריכות דרך XMP",
    };
  }

  if (catalog) {
    return {
      state: "ready",
      label: catalogStatus(catalog),
      source: "עריכות דרך Lightroom Catalog",
    };
  }

  if (profile) {
    return {
      state: "pending",
      label: "נבדק · אין חומר שמיש",
      source: "עריכות דרך XMP",
    };
  }

  return {
    state: "idle",
    label: "לא הוגדר",
    source: "XMP או Lightroom Catalog",
  };
}

function StatusPill({
  state,
  children,
}: {
  state: RouteState;
  children: ReactNode;
}) {
  const className =
    state === "ready"
      ? styles.statusReady
      : state === "pending"
        ? styles.statusPending
        : styles.statusIdle;

  return (
    <span className={className}>
      <span aria-hidden="true" />
      {children}
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

  const [jpegProfile, setJpegProfile] = useState<TestingProfile | null>(null);
  const [rawProfile, setRawProfile] = useState<TestingProfile | null>(null);
  const [catalogBindings, setCatalogBindings] = useState<
    Partial<Record<LearningMedia, CatalogBinding>>
  >({});
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const [firstNameDraft, setFirstNameDraft] = useState(identity.firstName);
  const [profileNameDraft, setProfileNameDraft] = useState(
    identity.profileName ?? "",
  );
  const [styleName, setStyleName] = useState("");
  const [presetPath, setPresetPath] = useState<string | null>(null);
  const [profileMode, setProfileMode] =
    useState<"from_source" | "explicit">("from_source");
  const [cameraProfile, setCameraProfile] = useState("");

  const applyOverview = useCallback((value: PhotographerSetupOverview) => {
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
      setCatalogBindings(loadCatalogBindings());
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "לא ניתן לטעון את הפרופיל.",
      );
    }
  }, [applyOverview]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function openLearning(media: LearningMedia) {
    writeTrainingEntry({ media });
    openView("training");
  }

  function openSettings() {
    setFirstNameDraft(identity.firstName);
    setProfileNameDraft(identity.profileName ?? "");
    setSettingsOpen(true);
  }

  async function choosePreset() {
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

  const jpegCatalog = catalogBindings.jpeg;
  const rawCatalog = catalogBindings.raw;
  const rawLearning = rawStatus(rawProfile, rawCatalog);

  const jpegConfigured =
    Number(Boolean(jpegProfile)) + Number(Boolean(jpegCatalog));
  const rawConfigured = Number(Boolean(rawProfile) || Boolean(rawCatalog));
  const totalConfigured = jpegConfigured + rawConfigured;

  const profileStatus = useMemo(() => {
    if (totalConfigured === 0) return "עדיין לא הוגדר";
    if (jpegConfigured === 2 && rawConfigured === 1) {
      return "כל מסלולי הלמידה הוגדרו";
    }
    return "בתהליך בנייה";
  }, [jpegConfigured, rawConfigured, totalConfigured]);

  return (
    <section className={styles.screen}>
      <header className={styles.profileHeader}>
        <div className={styles.profileIdentity}>
          <span className={styles.eyebrow}>הפרופיל שלי</span>
          <h1>סגנון העריכה של {profileOwnerLabel}</h1>
          <p>
            כאן רואים רק את מצב הלמידה שלך. JPEG ו־RAW נשמרים בנפרד,
            וכל מסלול מציג רק מידע שבאמת נמדד.
          </p>
        </div>

        <div className={styles.headerControls}>
          <div className={styles.profileStatus}>
            <span
              className={totalConfigured > 0 ? styles.readyDot : styles.pendingDot}
              aria-hidden="true"
            />
            <div>
              <small>מצב הפרופיל</small>
              <strong>{profileStatus}</strong>
            </div>
          </div>

          <button
            className={styles.settingsButton}
            type="button"
            aria-label="הגדרות הפרופיל"
            title="הגדרות הפרופיל"
            onClick={openSettings}
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

      <section className={styles.coveragePanel} aria-label="מצב מסלולי הלמידה">
        <div className={styles.coverageSummary}>
          <span className={styles.sectionKicker}>LEARNING COVERAGE</span>
          <div className={styles.coverageValue}>
            <strong>{totalConfigured}</strong>
            <span>/ 3</span>
          </div>
          <small>יכולות למידה הוגדרו</small>
        </div>

        <div className={styles.coverageRail}>
          <div
            className={
              routeState(jpegProfile) === "ready"
                ? styles.coverageItemReady
                : styles.coverageItem
            }
          >
            <span className={styles.coverageIndex}>01</span>
            <div>
              <strong>JPEG · לפני + אחרי</strong>
              <small>{jpegPairStatus(jpegProfile)}</small>
            </div>
            <span className={styles.coverageDot} aria-hidden="true" />
          </div>

          <div
            className={
              jpegCatalog ? styles.coverageItemReady : styles.coverageItem
            }
          >
            <span className={styles.coverageIndex}>02</span>
            <div>
              <strong>JPEG · Lightroom</strong>
              <small>{catalogStatus(jpegCatalog)}</small>
            </div>
            <span className={styles.coverageDot} aria-hidden="true" />
          </div>

          <div
            className={
              rawLearning.state === "ready"
                ? styles.coverageItemReady
                : styles.coverageItem
            }
          >
            <span className={styles.coverageIndex}>03</span>
            <div>
              <strong>RAW · Lightroom</strong>
              <small>{rawLearning.label}</small>
            </div>
            <span className={styles.coverageDot} aria-hidden="true" />
          </div>
        </div>
      </section>

      <section className={styles.learningSurface}>
        <article className={`${styles.learningPane} ${styles.jpegPane}`}>
          <header className={styles.paneHeader}>
            <div className={styles.paneIdentity}>
              <span className={styles.mediaMonogram}>J</span>
              <div>
                <span className={styles.paneEyebrow}>JPEG LEARNING</span>
                <h2>למידה לפי JPEG</h2>
                <p>שני מנגנוני למידה עצמאיים לאותו workflow.</p>
              </div>
            </div>

            <button
              className={styles.paneAction}
              type="button"
              onClick={() => openLearning("jpeg")}
            >
              <span>{jpegConfigured > 0 ? "המשך הגדרה" : "התחל הגדרה"}</span>
              <span aria-hidden="true">←</span>
            </button>
          </header>

          <div className={styles.capabilityTable}>
            <div className={styles.capabilityRow}>
              <span className={styles.capabilityNumber}>01</span>
              <div className={styles.capabilityMain}>
                <strong>זוגות לפני + אחרי</strong>
                <small>JPEG מקור מול JPEG סופי ערוך</small>
              </div>
              <div className={styles.capabilityStatus}>
                <span>PAIRS</span>
                <StatusPill state={routeState(jpegProfile)}>
                  {jpegPairStatus(jpegProfile)}
                </StatusPill>
              </div>
            </div>

            <div className={styles.capabilityRow}>
              <span className={styles.capabilityNumber}>02</span>
              <div className={styles.capabilityMain}>
                <strong>Lightroom Catalog</strong>
                <small>JPEG מקור + החלטות עריכה מתוך LRCAT</small>
              </div>
              <div className={styles.capabilityStatus}>
                <span>LRCAT</span>
                <StatusPill state={jpegCatalog ? "ready" : "idle"}>
                  {catalogStatus(jpegCatalog)}
                </StatusPill>
              </div>
            </div>
          </div>

          <footer className={styles.paneFooter}>
            <span>
              {jpegConfigured}/2
              <small> מסלולים הוגדרו</small>
            </span>
            <span className={styles.footerRule} />
            <small>כל מסלול נשמר ונמדד בנפרד</small>
          </footer>
        </article>

        <article className={`${styles.learningPane} ${styles.rawPane}`}>
          <header className={styles.paneHeader}>
            <div className={styles.paneIdentity}>
              <span className={styles.mediaMonogram}>R</span>
              <div>
                <span className={styles.paneEyebrow}>RAW LEARNING</span>
                <h2>למידה לפי RAW</h2>
                <p>Brain אחד שמבוסס על החלטות Lightroom.</p>
              </div>
            </div>

            <button
              className={styles.paneAction}
              type="button"
              onClick={() => openLearning("raw")}
            >
              <span>{rawConfigured ? "המשך הגדרה" : "התחל הגדרה"}</span>
              <span aria-hidden="true">←</span>
            </button>
          </header>

          <div className={styles.capabilityTable}>
            <div className={styles.capabilityRow}>
              <span className={styles.capabilityNumber}>01</span>
              <div className={styles.capabilityMain}>
                <strong>RAW + Lightroom</strong>
                <small>{rawLearning.source}</small>
              </div>
              <div className={styles.capabilityStatus}>
                <span>RAW</span>
                <StatusPill state={rawLearning.state}>
                  {rawLearning.label}
                </StatusPill>
              </div>
            </div>
          </div>

          <div className={styles.sourceStrip}>
            <span className={styles.sourceLabel}>מקורות עריכה</span>
            <span className={rawProfile ? styles.sourceActive : styles.sourceChip}>
              XMP
            </span>
            <span className={rawCatalog ? styles.sourceActive : styles.sourceChip}>
              LRCAT
            </span>
          </div>

          <footer className={styles.paneFooter}>
            <span>
              {rawConfigured}/1
              <small> מסלול הוגדר</small>
            </span>
            <span className={styles.footerRule} />
            <small>XMP ו־LRCAT הם מקורות לאותו Brain</small>
          </footer>
        </article>
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
                <span className={styles.eyebrow}>הגדרות פרופיל</span>
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
                  <strong>זהות</strong>
                  <small>
                    השדות האלה כבר משתמשים ב־Account Identity שמוכן לחיבור לחשבון עתידי.
                  </small>
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

              <details className={styles.advancedSettings}>
                <summary>
                  <span>
                    <strong>הגדרות מתקדמות</strong>
                    <small>סגנון, פריסט ופרופיל צבע</small>
                  </span>
                  <span aria-hidden="true">⌄</span>
                </summary>

                <div className={styles.advancedBody}>
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
                </div>
              </details>
            </div>

            <footer className={styles.modalFooter}>
              <span>
                שלום {firstNameDraft.trim() || "צלם"}, · סגנון העריכה של{" "}
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
