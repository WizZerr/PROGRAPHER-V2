export type LearningMedia = "jpeg" | "raw";
export type LearningMethod = "pairs" | "catalog";

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

export function writeTrainingEntry(entry: TrainingEntry) {
  try {
    window.sessionStorage.setItem(ENTRY_KEY, JSON.stringify(entry));
  } catch {
    // Navigation remains functional when session storage is unavailable.
  }
}

export function consumeTrainingEntry(): TrainingEntry | null {
  try {
    const value = window.sessionStorage.getItem(ENTRY_KEY);
    if (!value) return null;
    window.sessionStorage.removeItem(ENTRY_KEY);
    const parsed = JSON.parse(value) as Partial<TrainingEntry>;
    if (parsed.media !== "jpeg" && parsed.media !== "raw") return null;
    if (
      parsed.method !== undefined &&
      parsed.method !== "pairs" &&
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
