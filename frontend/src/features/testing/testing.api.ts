import { apiRequest } from "@/lib/api";

export type RecipeValues = {
  exposure: number | null;
  temperature: number | null;
  tint: number | null;
  process_version: string | null;
  camera_profile: string | null;
};

export type BaselineValues = {
  exposure: number;
  temperature: number;
  tint: number;
  sample_count: number;
  strategy: "median";
};

export type LearningSource = "raw" | "jpeg";

export type TestingProfile = {
  profile_id: string;
  created_at: string;
  photographer_id: string;
  learning_source: LearningSource;
  learning_material: "raw_xmp" | "jpeg_pairs";
  dataset_manifest_path: string | null;
  raw_root: string;
  edits_root: string;
  event_label: string;
  raw_files: number;
  xmp_files: number;
  matched_pairs: number;
  ambiguous_raw: number;
  unmatched_raw: number;
  usable_pairs: number;
  excluded_local_adjustments: number;
  excluded_missing_targets: number;
  baseline: BaselineValues | null;
  quality_claim_allowed: boolean;
  warnings: string[];
  note: string;
};

export type ReviewFile = {
  fingerprint: string;
  filename: string;
  relative_path: string;
  absolute_path: string;
  pair_status: string;
  photographer: RecipeValues | null;
  baseline: RecipeValues | null;
  saved_review: RecipeValues | null;
  suggested: RecipeValues | null;
  exclusion_reasons: string[];
};

export type ReviewSheet = {
  event_id: string;
  event_name: string;
  learning_source: LearningSource;
  quality_claim_allowed: boolean;
  baseline: BaselineValues | null;
  files: ReviewFile[];
  note: string;
};

export type ExportResult = {
  event_id: string;
  output_dir: string;
  written: number;
  skipped: number;
  files: Array<{
    fingerprint: string;
    status: "written" | "skipped";
    path: string | null;
    reason: string | null;
    source_unchanged: boolean;
  }>;
  note: string;
};

export async function getTestingProfile(
  learningSource?: LearningSource,
): Promise<TestingProfile | null> {
  try {
    const query = learningSource
      ? `?learning_source=${encodeURIComponent(learningSource)}`
      : "";
    return await apiRequest<TestingProfile>(`/api/testing/profile${query}`);
  } catch (error) {
    if (error instanceof Error && error.message.includes("אין פרופיל")) {
      return null;
    }
    throw error;
  }
}

export async function activateTestingProfile(
  learningSource: LearningSource,
): Promise<TestingProfile> {
  return apiRequest<TestingProfile>("/api/testing/profile/activate", {
    method: "POST",
    body: JSON.stringify({ learning_source: learningSource }),
  });
}

export async function createTestingProfile(input: {
  raw_root: string;
  edits_root: string;
  photographer_id: string;
  event_label: string;
  learning_source: LearningSource;
}): Promise<TestingProfile> {
  return apiRequest<TestingProfile>("/api/testing/profile", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function getReviewSheet(eventId: string): Promise<ReviewSheet> {
  return apiRequest<ReviewSheet>(`/api/testing/events/${eventId}/review`);
}

export async function exportRecipes(input: {
  event_id: string;
  output_dir: string;
  items: Array<{
    fingerprint: string;
    exposure: number;
    temperature: number;
    tint: number;
    decision: "approved" | "corrected";
  }>;
}): Promise<ExportResult> {
  return apiRequest<ExportResult>("/api/testing/export", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
