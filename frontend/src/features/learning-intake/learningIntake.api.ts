import { apiRequest } from "@/lib/api";

export type ColorMode = "color" | "black_white";
export type CatalogIntake = {
  catalog_path: string;
  smart_previews_path: string | null;
  raw_fallback_path: string | null;
  source_status: "smart_previews_unverified" | "raw_fallback_unverified" | "catalog_only_limited";
  audited_at: string;
  /** Numeric summary of the last analysis (links, edits, style, expected savings); null until analysed. */
  analysis: CatalogAnalysisSummary | null;
  analyzed_at: string | null;
  aggregate: {
    schema: string;
    catalog_photo_records: number;
    catalog_raw_records: number;
    parsed_raw_records: number;
    candidate_folder_day_groups: number;
    exclusions: Record<string, number>;
    training_ready_samples: number;
    warnings: string[];
  };
};

export type LearningProfile = {
  profile_id: string;
  name: string;
  photography_type: string;
  color_mode: ColorMode;
  status: "waiting_for_catalog" | "catalog_review";
  created_at: string;
  training_ready_samples: number;
  starting_point_verified: boolean;
  catalogs: CatalogIntake[];
};

export type CatalogDiscoveryCandidate = {
  catalog_path: string;
  smart_previews_path: string | null;
  preview_detection: "name_match_unverified" | "not_found";
};

export type CatalogDiscoveryResult = {
  catalogs: CatalogDiscoveryCandidate[];
  requires_selection: boolean;
  note: string;
};

export async function discoverCatalogLocation(path: string): Promise<CatalogDiscoveryResult> {
  return apiRequest<CatalogDiscoveryResult>("/api/learning-intake/discover", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export async function listLearningProfiles(): Promise<LearningProfile[]> {
  const response = await apiRequest<{ profiles: LearningProfile[] }>("/api/learning-intake/profiles");
  return response.profiles;
}

export async function deleteLearningProfile(profileId: string): Promise<void> {
  await apiRequest<void>(
    `/api/learning-intake/profiles/${encodeURIComponent(profileId)}`,
    { method: "DELETE" },
  );
}

export async function createLearningProfile(input: {
  name: string;
  photography_type: string;
  color_mode: ColorMode;
  consent: boolean;
}): Promise<LearningProfile> {
  return apiRequest<LearningProfile>("/api/learning-intake/profiles", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function attachLearningCatalog(profileId: string, input: {
  catalog_path: string;
  smart_previews_path: string | null;
  raw_fallback_path: string | null;
}): Promise<LearningProfile> {
  return apiRequest<LearningProfile>(
    `/api/learning-intake/profiles/${encodeURIComponent(profileId)}/catalogs`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export type StyleSlider = {
  key: string;
  /** fixed = same value on every photo (preset), per_photo = adjusted photo by photo, untouched = left at 0,
   * rare = set on fewer than half of the photos. */
  kind: "fixed" | "per_photo" | "untouched" | "rare";
  median: number;
  p10: number;
  p90: number;
  present: number;
};

export type CatalogAnalysisSummary = {
  schema: string;
  photos: number;
  smart_preview_files: number;
  linked: number;
  link_status_counts: Record<string, number>;
  pairs: number;
  /** Photos the editor turned black & white, left out of the style (schema v2 and later). */
  black_and_white_pairs?: number;
  pair_exclusions: Record<string, number>;
  other_edit_counts: Record<string, number>;
  folder_groups: number;
  style: StyleSlider[];
  backtest_exclusions: Record<string, number>;
  savings: {
    anchors: number;
    photos: number;
    proposed_photos?: number;
    untouched_pct?: number;
    no_correction_untouched_pct?: number;
    exposure_ok_pct?: number;
    temperature_ok_pct?: number;
    tint_ok_pct?: number;
    curve?: { anchors: number; untouched_pct: number }[];
  };
  training_ready_samples: 0;
};

export type AnalysisSample = {
  file_name: string;
  photographer: { exposure: number; temperature_k: number; tint: number };
  proposed: { exposure: number; temperature_k: number; tint: number };
  untouched: boolean;
  thumbnail_jpeg_base64: string | null;
  width: number | null;
  height: number | null;
};

export type CatalogAnalysisResult = {
  summary: CatalogAnalysisSummary;
  /** Shown once after an analysis; never stored. */
  samples: AnalysisSample[];
  profile: LearningProfile;
};

export async function analyzeCatalog(profileId: string, catalogPath: string): Promise<CatalogAnalysisResult> {
  return apiRequest<CatalogAnalysisResult>(
    `/api/learning-intake/profiles/${encodeURIComponent(profileId)}/analyze`,
    { method: "POST", body: JSON.stringify({ catalog_path: catalogPath }) },
  );
}
