export type LearningMedia = "jpeg" | "raw";
export type LearningMethod = "pairs" | "xmp" | "catalog";

export type TrainingEntry = {
  media: LearningMedia;
  method?: LearningMethod;
};

export type CatalogBinding = {
  sourceRoot: string;
  catalogPath: string;
  catalogPhotoRecords: number | null;
  updatedAt: string;
};

type CatalogBindings = Partial<Record<LearningMedia, CatalogBinding>>;

const ENTRY_KEY = "prographer.training.entry.v2";
const CATALOG_KEY = "prographer.training.catalog-bindings.v1";

let pendingEntry: TrainingEntry | null = null;

export function writeTrainingEntry(entry: TrainingEntry) {
  pendingEntry = entry;

  try {
    window.sessionStorage.setItem(ENTRY_KEY, JSON.stringify(entry));
  } catch {
    // Same-runtime navigation still works through pendingEntry.
  }
}

export function consumeTrainingEntry(): TrainingEntry | null {
  if (pendingEntry) {
    const entry = pendingEntry;
    pendingEntry = null;

    try {
      window.sessionStorage.removeItem(ENTRY_KEY);
    } catch {
      // The in-memory handoff is already consumed.
    }

    return entry;
  }

  try {
    const value = window.sessionStorage.getItem(ENTRY_KEY);
    if (!value) return null;
    window.sessionStorage.removeItem(ENTRY_KEY);
    const parsed = JSON.parse(value) as Partial<TrainingEntry>;
    if (parsed.media !== "jpeg" && parsed.media !== "raw") return null;
    if (
      parsed.method !== undefined &&
      parsed.method !== "pairs" &&
      parsed.method !== "xmp" &&
      parsed.method !== "catalog"
    ) {
      return null;
    }
    return {
      media: parsed.media,
      method: parsed.method,
    };
  } catch {
    return null;
  }
}

export function loadCatalogBindings(): CatalogBindings {
  try {
    const value = window.localStorage.getItem(CATALOG_KEY);
    if (!value) return {};
    const parsed = JSON.parse(value) as CatalogBindings;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function saveCatalogBinding(
  media: LearningMedia,
  binding: CatalogBinding,
) {
  const current = loadCatalogBindings();
  const next = { ...current, [media]: binding };
  try {
    window.localStorage.setItem(CATALOG_KEY, JSON.stringify(next));
  } catch {
    // Temporary local preparation state until account-backed learning metadata exists.
  }
  return next;
}
