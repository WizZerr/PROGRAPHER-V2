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


export type SourceSample = {
  catalog_image_id: number | string;
  catalog_global_image_id: string | null;
  filename: string;
  capture_day: string;
  candidate_group: string;
  develop_parse_ok: boolean;
  develop_fields: string[];
  virtual_copy_candidate: boolean;
  issues: string[];
  source_match_status: string;
  source_candidate_path: string | null;
  source_sha256: string | null;
  source_identity_verified: false;
  photographer_finality_verified: false;
  import_reset_baseline_verified: false;
  event_identity_verified: false;
  training_eligible: false;
};

export type PreflightSampleReport = {
  schema: string;
  status: string;
  catalog_path: string;
  sample_count: number;
  sample_limit: number;
  group_count_in_sample: number;
  source_match_counts: Record<string, number>;
  source_identity_verified_count: number;
  finality_verified_count: number;
  training_ready_samples: number;
  records: SourceSample[];
  warnings: string[];
};

export async function runSamplePreflight(
  profileId: string,
  input: { catalog_path: string; raw_folder: string | null; sample_size?: number },
): Promise<PreflightSampleReport> {
  return apiRequest<PreflightSampleReport>(
    `/api/learning-intake/profiles/${encodeURIComponent(profileId)}/sample-preflight`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export type SmartPreviewContentReport = {
  schema: string;
  status: "DNG_CONTENT_PILOT_ONLY" | "SMART_PREVIEWS_NOT_CONFIGURED";
  source_kind: "smart_previews";
  counts: Record<string, number>;
  decode_attempts: number;
  decode_status_counts: Record<string, number>;
  decode_compression_counts?: Record<string, number>;
  reset_render_counts?: Record<string, number>;
  decoded_samples: {
    state: string;
    width: number;
    height: number;
    preview_mean_luma?: number;
    preview_mean_linear?: number;
    compression_code?: number;
    opcodes_applied?: number;
    opcodes_ignored?: number;
    embedded_profile_present?: boolean;
    /** Unedited "before" image as Lightroom shows it after Reset; in memory only, never saved. */
    reset_render?: {
      state: string;
      width?: number;
      height?: number;
      mean_srgb_luma?: number;
      calibration_stops?: number;
      /** "adobe_color_xmp" (validated setup) or "smart_preview_profile" (fallback when Lightroom's file is absent). */
      look_source?: "adobe_color_xmp" | "smart_preview_profile";
      /** "applied" | "no_lens_metadata" | "lens_profile_not_found". */
      lens_vignetting?: string;
      thumbnail_jpeg_base64?: string;
    };
  }[];
  catalog_photo_identity_verified: false;
  photo_to_dng_link_verified: false;
  source_only_neutral_parity_verified: false;
  photographer_finality_verified: false;
  training_ready_samples: 0;
  warnings: string[];
};

export async function probeSmartPreviewContents(
  profileId: string,
  catalogPath: string,
): Promise<SmartPreviewContentReport> {
  return apiRequest<SmartPreviewContentReport>(
    `/api/learning-intake/profiles/${encodeURIComponent(profileId)}/smart-preview-probe`,
    { method: "POST", body: JSON.stringify({ catalog_path: catalogPath }) },
  );
}

export type SmartPreviewSdkLinkReview = {
  schema: string;
  status: "SDK_PATH_CORROBORATION_RESEARCH_ONLY";
  selected_count: number;
  sdk_path_catalog_uuid_correlated: number;
  shared_preview_extra_links: number;
  status_counts: Record<string, number>;
  records: {
    catalog_uuid: string;
    status: string;
    virtual_copy_requires_review: boolean;
    final_edit_verified: false;
    neutral_start_verified: false;
    training_eligible: false;
  }[];
  source_raw_identity_verified: false;
  approved_finality_verified: false;
  neutral_start_verified: false;
  training_ready_samples: 0;
  warnings: string[];
};

export async function reviewSmartPreviewSdkLinks(
  profileId: string, catalogPath: string, evidencePath: string,
): Promise<SmartPreviewSdkLinkReview> {
  return apiRequest<SmartPreviewSdkLinkReview>(
    `/api/learning-intake/profiles/${encodeURIComponent(profileId)}/smart-preview-sdk-review`,
    { method: "POST", body: JSON.stringify({
      catalog_path: catalogPath, evidence_path: evidencePath,
    }) },
  );
}
