import { apiRequest } from "@/lib/api";

export type ColorMode = "color" | "black_white";
export type CatalogIntake = {
  catalog_path: string;
  smart_previews_path: string | null;
  raw_fallback_path: string | null;
  source_status: "smart_previews_unverified" | "raw_fallback_unverified" | "catalog_only_limited";
  audited_at: string;
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

export async function listLearningProfiles(): Promise<LearningProfile[]> {
  const response = await apiRequest<{ profiles: LearningProfile[] }>("/api/learning-intake/profiles");
  return response.profiles;
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
