"use client";

import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";

type AuthUser = {
  id: string;
  email: string;
  display_name: string;
  studio_name: string;
  onboarding_completed: boolean;
  created_at: string;
};

type OnboardingProfile = {
  specialties: string[];
  editor_software: string;
  style_words: string[];
  priorities: string[];
  notes: string;
  completed: boolean;
};

type ViewId =
  | "dashboard"
  | "events"
  | "new-event"
  | "style"
  | "style-setup"
  | "diagnostics"
  | "profile"
  | "review"
  | "lab"
  | "system"
  | "event-detail"
  | "training-review"
  | "photo-detail";

type ApiEvent = {
  id: string;
  name: string;
  event_type: string;
  event_date?: string | null;
  style_note?: string | null;
  status: string;
  photo_count?: number;
  preview_count?: number;
  created_at: string;
};

type PhotoMetadata = {
  file_type?: string;
  is_raw?: boolean;
  camera_make?: string | null;
  camera_model?: string | null;
  lens?: string | null;
  iso?: string | null;
  aperture?: string | null;
  shutter_speed?: string | null;
  focal_length?: string | null;
  date_taken?: string | null;
  width?: number | null;
  height?: number | null;
  metadata_source?: string;
};

type CanonicalRecipe = {
  exposure?: number;
  contrast?: number;
  highlights?: number;
  shadows?: number;
  whites?: number;
  blacks?: number;
  temperature?: number;
  tint?: number;
  clarity?: number;
  vibrance?: number;
  saturation?: number;
  brightness?: number;
  recovery?: number;
  fill_light?: number;
};

type RetrainingStatus = {
  ok: boolean;
  retraining_format: string;
  active_profile: {
    registry_id: string;
    name?: string | null;
    version_id: string;
    version_number: number;
    profile_format?: string | null;
    recipe_contract_version?: string | null;
    activated_at?: string | null;
  } | null;
  readiness: {
    sample_count: number;
    approved_count: number;
    corrected_count: number;
    minimum_samples: number;
    minimum_new_samples: number;
    new_samples_since_active: number;
    remaining_samples: number;
    ready: boolean;
    active_is_adaptive: boolean;
    recipe_contract_version: string;
  };
  latest_run: {
    id: string;
    status: string;
    stage: string;
    progress_percent: number;
    sample_count: number;
    train_count: number;
    validation_count: number;
    adapted_targets: string[];
    metrics?: {
      mean_selected_validation_improvement_percent?: number;
      target_metrics?: Record<
        string,
        {
          status: string;
          validation_improvement_percent?: number;
        }
      >;
    };
    candidate_version_id?: string | null;
    error?: string;
  } | null;
  candidate_version: {
    id: string;
    version_number: number;
    status: string;
    recipe_contract_version: string;
    summary?: {
      adapted_target_count?: number;
      adapted_targets?: string[];
      learning_samples?: number;
      mean_selected_validation_improvement_percent?: number;
    };
    created_at: string;
    activated_at?: string | null;
  } | null;
};

type ProductionLearningDecision = {
  id: string;
  user_id: string;
  registry_id: string;
  profile_version_id: string;
  profile_version_number: number;
  prediction_id: string | null;
  source_photo_id: string | null;
  source_event_id: string | null;
  brain_analysis_id: string | null;
  verdict: "approved" | "corrected";
  recipe_contract_version: string;
  process_family: "legacy" | "modern" | "unknown";
  ai_recipe: CanonicalRecipe;
  photographer_recipe: CanonicalRecipe;
  delta: CanonicalRecipe;
  changed_parameters: string[];
  changed_parameter_count: number;
  final_render_path?: string | null;
  final_render_url?: string | null;
  is_current: boolean;
  supersedes_sample_id?: string | null;
  created_at: string;
  updated_at: string;
};

type ProductionDarkroomPayload = {
  ok: boolean;
  darkroom_mode: "production_profile";
  process_family: "legacy" | "modern" | "unknown";
  preview_notice: string;
  recipe_contract: {
    version: string;
    temperature_semantics: string;
  };
  prediction: AiPredictionSummary & {
    recipe: CanonicalRecipe;
    provenance?: Record<string, unknown>;
  };
  render: {
    id: string;
    rendered_url: string;
    rendered_path: string;
    process_family: string;
    preview_is_approximation: boolean;
    created_at: string;
  };
  prediction_reused: boolean;
  render_reused: boolean;
};

type AnalysisPayload = {
  metrics: {
    mean_brightness: number;
    contrast_std: number;
    highlight_clip_percent: number;
    shadow_clip_percent: number;
    mean_saturation_percent: number;
    warmth_score: number;
  };
  assessment: {
    exposure_state: string;
    color_state: string;
    dynamic_range_state: string;
    readiness: string;
    summary_he: string;
    confidence_percent: number;
    analysis_source: string;
  };
  recipe: {
    exposure: number;
    highlights: number;
    shadows: number;
    whites: number;
    blacks: number;
    contrast: number;
    temperature: number;
    vibrance: number;
    clarity: number;
  };
  base_recipe?: {
    exposure: number;
    highlights: number;
    shadows: number;
    whites: number;
    blacks: number;
    contrast: number;
    temperature: number;
    vibrance: number;
    clarity: number;
  };
  style_dna?: StyleDnaSummary;
};

type StyleDnaSummary = {
  version: number;
  sample_count: number;
  correction_count: number;
  approval_count: number;
  default_count?: number;
  confidence_percent: number;
  learning_strength_percent: number;
  bias: AnalysisPayload["recipe"];
  raw_average_delta?: AnalysisPayload["recipe"];
  average_abs_delta?: AnalysisPayload["recipe"];
  top_adjustments: Array<{
    key: string;
    label: string;
    bias: number;
    raw_average_delta: number;
  }>;
  status_he: string;
};

type FeedbackVerdict = "approved" | "needs_changes" | "selected_default" | "selected_final" | "corrected";

type AiPredictionSummary = {
  id: string;
  photo_id: string;
  event_id: string;
  profile_version_id: string;
  profile_version_number: number;
  recipe_contract_version: string;
  recipe?: CanonicalRecipe;
  created_at: string;
};

type EventCompletionStatus = {
  ok: boolean;
  export_format: string;
  event_id: string;
  event_name: string;
  event_status: string;
  total_photos: number;
  predicted_photos: number;
  decided_photos: number;
  approved_photos: number;
  corrected_photos: number;
  remaining_predictions: number;
  remaining_decisions: number;
  missing_prediction_names: string[];
  missing_decision_names: string[];
  ready_to_complete: boolean;
  completed: boolean;
  decision_fingerprint?: string | null;
  export_up_to_date: boolean;
  latest_export?: {
    id: string;
    event_id: string;
    export_format: string;
    status: string;
    file_name: string;
    photo_count: number;
    approved_count: number;
    corrected_count: number;
    profile_versions: number[];
    decision_fingerprint: string;
    created_at: string;
  } | null;
};

type EventInferenceStatus = {
  ok: boolean;
  event_id: string;
  active_profile: {
    registry_id: string;
    name?: string | null;
    version_id: string;
    version_number: number;
    profile_format?: string | null;
    recipe_contract_version?: string | null;
    activated_at?: string | null;
  } | null;
  coverage: {
    total_photos: number;
    eligible_photos: number;
    predicted_photos: number;
    missing_photos: number;
    progress_percent: number;
    complete: boolean;
  };
  job: {
    id: string;
    status: string;
    stage: string;
    progress_percent: number;
    total_photos: number;
    processed_photos: number;
    predicted_photos: number;
    reused_photos: number;
    failed_photos: number;
    details?: {
      message?: string;
      current_photo?: string;
    };
    error?: string;
  } | null;
};

type ApiPhoto = {
  id: string;
  event_id: string;
  original_name: string;
  original_path: string;
  preview_path?: string | null;
  preview_url?: string | null;
  edited_path?: string | null;
  edited_url?: string | null;
  file_size: number;
  width?: number | null;
  height?: number | null;
  status: string;
  extension?: string;
  is_raw?: boolean;
  metadata?: PhotoMetadata;
  latest_analysis?: {
    id: string;
    photo_id: string;
    analysis_json: string;
    recipe_json: string;
    created_at: string;
  } | null;
  latest_render?: {
    id: string;
    photo_id: string;
    recipe_json: string;
    rendered_path: string;
    width: number;
    height: number;
    created_at: string;
  } | null;
  latest_ai_prediction?: AiPredictionSummary | null;
  latest_ai_learning_decision?: ProductionLearningDecision | null;
  latest_ai_preview_render?: {
    id: string;
    rendered_url: string;
    rendered_path: string;
    process_family: string;
    preview_is_approximation: boolean;
    created_at: string;
  } | null;
  active_ai_profile?: EventInferenceStatus["active_profile"] | null;
  latest_feedback?: {
    id: string;
    photo_id: string;
    verdict: FeedbackVerdict;
    ai_recipe?: string | null;
    photographer_recipe?: string | null;
    note?: string | null;
    created_at: string;
  } | null;
  created_at: string;
};

type GalleryResponse = {
  event: ApiEvent;
  summary: {
    photo_count: number;
    raw_count: number;
    preview_count: number;
    ai_prediction_count?: number;
    total_bytes: number;
  };
  photos: ApiPhoto[];
};

type TrainingReviewItem = {
  rank: number;
  photo_id: string;
  original_name: string;
  preview_url?: string | null;
  extension?: string | null;
  metadata?: PhotoMetadata;
  scene?: { key?: string; label_he?: string; score_percent?: number };
  lighting?: { key?: string; label_he?: string; score_percent?: number };
  people?: { key?: string; label_he?: string; score_percent?: number };
  framing?: { key?: string; label_he?: string; score_percent?: number };
  technical?: { key?: string; label_he?: string; score_percent?: number };
  visual_distance_percent: number;
  selection_reason: string;
  reviewed: boolean;
  feedback_verdict?: FeedbackVerdict | null;
};

type TrainingReviewResponse = {
  ok: boolean;
  event: ApiEvent;
  requested_count: number;
  analyzed_photos: number;
  selected_count: number;
  reviewed_count: number;
  remaining_count: number;
  semantic_combinations: number;
  method: string;
  items: TrainingReviewItem[];
};

type LightroomCatalogCard = {
  name: string;
  path: string;
  source: string;
  size_bytes: number;
  size_mb: number;
  modified_at: string;
  has_lrcat_data: boolean;
  has_wal: boolean;
};

type LightroomCollection = {
  id: string;
  name: string;
  path?: string;
  photo_count: number | null;
  source_table: string;
  recommended?: boolean;
  is_group?: boolean;
  is_system?: boolean;
};

type LightroomTrainingGroup = {
  id: string;
  name: string;
  display_name?: string;
  path: string;
  photo_count: number;
  kind: "collection" | "virtual_copy_group" | string;
  recommended: boolean;
  badge_he?: string;
  style_score?: number;
  coverage_percent?: number;
  technical?: boolean;
};

type LightroomCatalogAnalysis = {
  ok: boolean;
  catalog: {
    name: string;
    path: string;
    size_bytes: number;
    size_mb: number;
    modified_at: string;
    has_lrcat_data: boolean;
  };
  summary: {
    source_photo_count: number;
    edited_source_photo_count: number;
    raw_count: number;
    jpeg_count: number;
    training_group_count: number;
    style_candidate_count?: number;
    recommended_group_count: number;
    technical_group_count?: number;
    files_available_count: number;
    files_available_percent: number;
    image_count: number;
    file_count: number;
    other_count: number;
    collection_count: number;
    develop_record_count: number;
    develop_table_count: number;
  };
  training_groups: LightroomTrainingGroup[];
  style_discovery?: {
    mode: "style_variants" | "collections" | "whole_catalog" | string;
    selection_mode: "single" | "multiple" | "none" | string;
    candidate_count: number;
    technical_group_count: number;
    raw_group_count: number;
    recommended_id?: string | null;
    auto_selected_id?: string | null;
    title_he: string;
    description_he: string;
  };
  readiness: {
    state: "ready" | "good" | "needs_attention" | string;
    score: number;
    message_he: string;
  };
  file_availability: {
    matched: number;
    total: number;
    percent: number;
    method: string;
  };
  file_types: {
    raw: number;
    jpeg: number;
    other: number;
    total_with_extension: number;
    breakdown: Record<string, number>;
  };
  collections: LightroomCollection[];
  develop: {
    develop_table_count: number;
    develop_record_count: number | null;
    final_settings_count?: number;
    history_step_count?: number;
    capabilities: string[];
    tables: Array<{ table: string; row_count: number | null; columns: string[] }>;
  };
  diagnostics?: {
    image_structure?: {
      image_records?: number;
      source_photos?: number;
      master_records?: number;
      virtual_copies?: number;
      edited_source_photos?: number;
      edited_image_versions?: number;
    };
  };
};

type LightroomDatasetAudit = {
  id: string;
  profile_import_id: string;
  dataset_build_id: string;
  user_id: string;
  status: "queued" | "building" | "completed" | "failed" | string;
  stage: string;
  stage_he: string;
  progress_percent: number;
  result: {
    audit_version?: string;
    passed?: boolean;
    integrity_percent?: number;
    checks_passed?: number;
    checks_total?: number;
    checks?: Array<{
      key: string;
      label_he: string;
      passed: boolean;
      critical: boolean;
      detail_he?: string;
      actual?: any;
      expected?: any;
    }>;
    summary?: {
      total_records?: number;
      valid_pairs?: number;
      invalid_pairs?: number;
      unique_source_files?: number;
      unique_target_edits?: number;
      normalized_recipes?: number;
      train?: number;
      validation?: number;
      test?: number;
      split_overlap?: number;
      selected_style?: string;
    };
    preview?: Array<{
      sample_id?: string;
      filename?: string;
      style?: string;
      split?: string;
      source_file_id?: string | number;
      lightroom_image_id?: string | number;
      lightroom_copy_name?: string;
      develop_recipe?: Record<string, any>;
    }>;
  };
  error: string;
  created_at: string;
  updated_at: string;
};

type LightroomDatasetBuild = {
  id: string;
  profile_import_id: string;
  user_id: string;
  status: "queued" | "building" | "completed" | "failed" | string;
  stage: string;
  stage_he: string;
  progress_percent: number;
  details: Record<string, any>;
  manifest: {
    target_records?: number;
    unique_source_targets?: number;
    source_files_found?: number;
    source_files_missing?: number;
    develop_payloads_found?: number;
    develop_payloads_missing?: number;
    normalized_recipes_parsed?: number;
    valid_pairs?: number;
    invalid_pairs?: number;
    splits?: { train: number; validation: number; test: number };
    test_locked?: boolean;
  };
  output_dir: string;
  error: string;
  created_at: string;
  updated_at: string;
};

type LightroomVisionJob = {
  id: string;
  profile_import_id: string;
  dataset_build_id: string;
  user_id: string;
  status: "queued" | "building" | "completed" | "failed" | string;
  stage: string;
  stage_he: string;
  progress_percent: number;
  details: {
    processed?: number;
    total?: number;
    failed?: number;
    train_processed?: number;
    validation_processed?: number;
    test_processed?: number;
    images_per_second?: number;
    eta_seconds?: number | null;
    device?: string;
    model_name?: string;
  };
  manifest: {
    model_name?: string;
    device?: string;
    embedding_dimensions?: number;
    total?: number;
    processed?: number;
    failed?: number;
    splits?: { train?: number; validation?: number; test?: number };
    test_locked?: boolean;
  };
  output_dir: string;
  error: string;
  created_at: string;
  updated_at: string;
};

type LightroomTrainingRun = {
  id: string;
  profile_import_id: string;
  vision_job_id: string;
  user_id: string;
  status: "queued" | "building" | "completed" | "failed" | string;
  stage: string;
  stage_he: string;
  progress_percent: number;
  details: Record<string, any>;
  metrics: {
    pipeline_version?: string;
    model_type?: string;
    feature_count?: number;
    target_count?: number;
    target_keys?: string[];
    train_samples?: number;
    validation_samples?: number;
    test_samples?: number;
    validation?: Record<string, {
      train_samples?: number;
      validation_samples?: number;
      validation_mae?: number;
      validation_baseline_mae?: number;
      validation_improvement_percent?: number;
    }>;
    test?: Record<string, {
      samples?: number;
      mae?: number;
      baseline_mae?: number;
      improvement_percent?: number;
    }>;
    test_opened_after_model_lock?: boolean;
  };
  model_path: string;
  error: string;
  created_at: string;
  updated_at: string;
};

type LightroomEvaluationSample = {
  sample_id: string;
  filename: string;
  source_path: string;
  split: string;
  target_style: Record<string, any>;
  composite_normalized_error: number;
  parameters: Record<string, {
    actual: number;
    predicted: number;
    abs_error: number;
    normalized_error: number;
  }>;
  metadata: {
    iso?: number;
    aperture?: number;
    shutter_seconds?: number;
    focal_length?: number;
    camera_model?: string;
    lens?: string;
  };
  vision_top: Record<string, any>;
};

type LightroomEvaluation = {
  evaluation_version: string;
  model_type: string;
  test_samples: number;
  trained_parameter_count: number;
  trained_parameters: string[];
  parameter_stats: Record<string, {
    samples: number;
    mae: number;
    median_abs_error: number;
    p90_abs_error: number;
    p95_abs_error: number;
    max_abs_error: number;
    baseline_value: number;
    baseline_mae: number;
    improvement_percent: number;
  }>;
  coverage: Record<string, {
    trained: boolean;
    reason: string;
    train_count: number;
    train_total: number;
    train_coverage_percent: number;
    validation_count: number;
    validation_total: number;
    test_count: number;
    test_total: number;
  }>;
  overall: {
    mean_parameter_improvement_percent: number;
    median_composite_normalized_error: number;
    p90_composite_normalized_error: number;
    test_was_locked: boolean;
  };
  feature_group_importance_percent: {
    embedding: number;
    metadata: number;
    semantic: number;
  };
  top_features: Array<{ name: string; importance: number }>;
  best_samples: LightroomEvaluationSample[];
  worst_samples: LightroomEvaluationSample[];
  representative_samples: LightroomEvaluationSample[];
  samples: LightroomEvaluationSample[];
};

type RecipeV2Report = {
  recipe_version: string;
  splits: { train: number; validation: number; test: number };
  total_samples: number;
  process_family_counts: { legacy: number; modern: number; unknown: number };
  coverage: Record<string, {
    v1_count_all_splits: number;
    v2_count_all_splits: number;
    v1_percent_all_splits: number;
    v2_percent_all_splits: number;
    train_count: number;
    train_percent: number;
    default_filled_all_splits: number;
    train_eligible: boolean;
  }>;
  distributions: Record<string, {
    count: number;
    min: number | null;
    p01: number | null;
    median: number | null;
    p90: number | null;
    p99: number | null;
    max: number | null;
    extreme_count: number;
  }>;
  temperature: {
    training_representation: string;
    native_unit: string;
    extremes_preserved: boolean;
  };
  provenance: Record<string, {
    top_source?: string | null;
    source_counts_all_splits: Record<string, number>;
    source_counts_train: Record<string, number>;
    explicit_count_train: number;
    default_count_train: number;
    v1_fallback_count_train: number;
    unknown_source_count_train: number;
    legacy_count_all_splits: number;
    modern_count_all_splits: number;
    unknown_family_count_all_splits: number;
    unique_value_count_train: number;
    value_range_train: number;
  }>;
  learnability: Record<string, {
    status: "trainable" | "constant" | "sparse" | "suspicious" | "unsupported" | string;
    reason: string;
    train_percent: number;
    train_count: number;
    train_total: number;
    constant_value?: number | null;
    top_source?: string | null;
    explicit_percent_train: number;
    default_percent_train: number;
    v1_fallback_percent_train: number;
    unique_value_count_train: number;
    value_range_train: number;
    dominant_value_train?: number | null;
    dominant_percent_train?: number;
    variation_support_count_train?: number;
    variation_support_percent_train?: number;
    minimum_variation_support_required?: number;
  }>;
  constant_profile_values: Record<string, number>;
  guard: {
    trainable_count: number;
    constant_count: number;
    sparse_count: number;
    suspicious_count: number;
    unsupported_count: number;
    ready_for_training: boolean;
    suspicious_targets_are_excluded: boolean;
    sparse_targets_are_excluded: boolean;
    constant_targets_are_stored_without_model_training: boolean;
    sparse_policy?: {
      minimum_absolute_variation_support: number;
      minimum_train_fraction: number;
      effective_required_for_this_dataset: number;
    };
  };
  rules: Record<string, any>;
};

type TrainingV2Run = {
  id: string;
  status: "queued" | "building" | "completed" | "failed" | string;
  stage: string;
  stage_he: string;
  progress_percent: number;
  details: Record<string, any>;
  metrics: {
    pipeline_version?: string;
    model_type?: string;
    target_count?: number;
    target_keys?: string[];
    constant_target_count?: number;
    constant_profile_values?: Record<string, number>;
    excluded_targets?: Record<string, any>;
    test?: Record<string, {
      samples?: number;
      mae_native?: number;
      baseline_mae_native?: number;
      improvement_percent?: number;
      training_transform?: string;
    }>;
    v1_vs_v2?: Record<string, {
      v1_mae?: number | null;
      v2_mae?: number;
      v2_vs_v1_improvement_percent?: number | null;
      new_in_v2?: boolean;
    }>;
  };
  model_path: string;
  error: string;
};

type PhotographerProfileOverview = {
  ok: boolean;
  format: string;
  profile_ready: boolean;
  active_profile: {
    registry_id: string;
    name: string;
    version_id: string;
    version_number: number;
    activated_at?: string | null;
    created_at?: string | null;
    recipe_contract_version: string;
  } | null;
  learning: {
    sample_count: number;
    approved_count: number;
    corrected_count: number;
    acceptance_rate: number | null;
  };
  growth: {
    ready_for_candidate: boolean;
    remaining_samples: number;
    minimum_samples: number;
    new_samples_since_active: number;
    latest_run_status?: string | null;
    latest_run_progress: number;
  } | null;
  candidate: {
    id: string;
    version_number: number;
    status: string;
    summary?: {
      adapted_target_count?: number;
      adapted_targets?: string[];
      learning_samples?: number;
      mean_selected_validation_improvement_percent?: number;
    };
    created_at: string;
    activated_at?: string | null;
  } | null;
  source: {
    kind: string;
    label: string;
    profile_import_id: string;
    profile_name: string;
    catalog_name?: string | null;
    status: string;
    created_at: string;
    updated_at: string;
  } | null;
  photographer_preferences: {
    specialties: string[];
    editor_software: string;
    style_words: string[];
    priorities: string[];
    notes: string;
    completed: boolean;
    updated_at?: string | null;
  };
};

type Stats = {
  events: number;
  photos: number;
  feedback_total: number;
  perfect_without_change: number;
  acceptance_rate: number | null;
  style_pairs: number;
  production_learning_samples?: number;
  production_corrected_samples?: number;
  production_learning_format?: string;
};

type SystemInfo = {
  cpu?: { percent?: number; logical_cores?: number; physical_cores?: number };
  ram?: { total_bytes?: number; used_bytes?: number; percent?: number };
  disk?: { path?: string; total_bytes?: number; used_bytes?: number; free_bytes?: number; percent?: number };
  gpu?: {
    available?: boolean;
    name?: string;
    memory_total_mb?: number;
    memory_used_mb?: number;
    utilization_percent?: number;
    temperature_c?: number;
  };
  raw_support?: boolean;
  exif_support?: boolean;
};

const MENU: Array<[ViewId, string]> = [
  ["dashboard", "לוח בקרה"],
  ["events", "אירועים"],
  ["new-event", "אירוע חדש"],
  ["style", "הסגנון שלי"],
  ["profile", "הפרופיל שלי"],
];

const API_BASE =
  process.env.NEXT_PUBLIC_PROGRAPHER_API_URL?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

function localTodayForInput() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatEventDate(value?: string | null) {
  if (!value) return "ללא תאריך";
  const parts = value.split("-");
  if (parts.length === 3) {
    const [year, month, day] = parts;
    return `${day}.${month}.${year}`;
  }
  return value;
}

function eventToneClass(eventType?: string | null) {
  const value = String(eventType || "").trim();
  if (value === "חתונה") return "toneWedding";
  if (value === "בר מצווה") return "toneBar";
  if (value === "בת מצווה") return "toneBat";
  if (value === "חינה") return "toneHenna";
  return "toneOther";
}

async function apiFetch(path: string, init?: RequestInit) {
  const sessionToken = typeof window !== "undefined" ? window.localStorage.getItem("prographer_session") : null;
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: { ...(init?.headers || {}), ...(sessionToken ? { Authorization: `Bearer ${sessionToken}` } : {}) },
  });
  if (!response.ok) {
    let message = `שגיאת API (${response.status})`;
    try { const body = await response.json(); if (body?.detail) message = String(body.detail); } catch {}
    throw new Error(message);
  }
  return response;
}

async function publicApiFetch(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init, cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    let message = `שגיאת API (${response.status})`;
    try { const body = await response.json(); if (body?.detail) message = String(body.detail); } catch {}
    throw new Error(message);
  }
  return response;
}

export default function Home() {
  const [view, setView] = useState<ViewId>("dashboard");
  const [engineOnline, setEngineOnline] = useState<boolean | null>(null);
  const [engineError, setEngineError] = useState("");
  const [events, setEvents] = useState<ApiEvent[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [styleDna, setStyleDna] = useState<StyleDnaSummary | null>(null);
  const [lightroomCatalogs, setLightroomCatalogs] = useState<LightroomCatalogCard[]>([]);
  const [lightroomScanLoading, setLightroomScanLoading] = useState(false);
  const [lightroomManualPath, setLightroomManualPath] = useState("");
  const [lightroomAnalyzeLoading, setLightroomAnalyzeLoading] = useState(false);
  const [lightroomAnalysis, setLightroomAnalysis] = useState<LightroomCatalogAnalysis | null>(null);
  const [lightroomSelectedCollections, setLightroomSelectedCollections] = useState<string[]>([]);
  const [lightroomProfileName, setLightroomProfileName] = useState("הפרופיל המקצועי שלי");
  const [lightroomDraftSaving, setLightroomDraftSaving] = useState(false);
  const [lightroomDatasetBuild, setLightroomDatasetBuild] = useState<LightroomDatasetBuild | null>(null);
  const [lightroomDatasetAudit, setLightroomDatasetAudit] = useState<LightroomDatasetAudit | null>(null);
  const [lightroomVisionJob, setLightroomVisionJob] = useState<LightroomVisionJob | null>(null);
  const [lightroomTrainingRun, setLightroomTrainingRun] = useState<LightroomTrainingRun | null>(null);
  const [lightroomTrainingStarting, setLightroomTrainingStarting] = useState(false);
  const [lightroomEvaluation, setLightroomEvaluation] = useState<LightroomEvaluation | null>(null);
  const [lightroomEvaluationLoading, setLightroomEvaluationLoading] = useState(false);
  const [evaluationSampleMode, setEvaluationSampleMode] = useState<"worst" | "best" | "representative">("worst");
  const [evaluationSelectedSampleId, setEvaluationSelectedSampleId] = useState("");
  const [recipeV2Report, setRecipeV2Report] = useState<RecipeV2Report | null>(null);
  const [recipeV2Loading, setRecipeV2Loading] = useState(false);
  const [trainingV2Run, setTrainingV2Run] = useState<TrainingV2Run | null>(null);
  const [trainingV2Starting, setTrainingV2Starting] = useState(false);
  const [lightroomActiveProfileId, setLightroomActiveProfileId] = useState("");
  const [loadingData, setLoadingData] = useState(false);
  const [authReady, setAuthReady] = useState(false);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authDisplayName, setAuthDisplayName] = useState("");
  const [authStudioName, setAuthStudioName] = useState("");
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [authMessage, setAuthMessage] = useState("");
  const [onboarding, setOnboarding] = useState<OnboardingProfile>({ specialties: [], editor_software: "", style_words: [], priorities: [], notes: "", completed: false });
  const [onboardingStep, setOnboardingStep] = useState(1);
  const [onboardingSaving, setOnboardingSaving] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ApiEvent | null>(null);
  const [keepLearningOnDelete, setKeepLearningOnDelete] = useState(true);
  const [deletingEvent, setDeletingEvent] = useState(false);

  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [gallery, setGallery] = useState<GalleryResponse | null>(null);
  const [galleryLoading, setGalleryLoading] = useState(false);
  const [eventInference, setEventInference] = useState<EventInferenceStatus | null>(null);
  const [eventInferenceStarting, setEventInferenceStarting] = useState(false);
  const [eventCompletion, setEventCompletion] = useState<EventCompletionStatus | null>(null);
  const [eventCompletionLoading, setEventCompletionLoading] = useState(false);
  const [trainingReview, setTrainingReview] = useState<TrainingReviewResponse | null>(null);
  const [trainingReviewLoading, setTrainingReviewLoading] = useState(false);
  const [trainingReviewCount, setTrainingReviewCount] = useState(48);
  const [photoReturnView, setPhotoReturnView] = useState<"event-detail" | "training-review">("event-detail");
  const [selectedPhoto, setSelectedPhoto] = useState<ApiPhoto | null>(null);
  const [photoLoading, setPhotoLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [renderLoading, setRenderLoading] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisPayload | null>(null);
  const [analysisCreatedAt, setAnalysisCreatedAt] = useState<string | null>(null);
  const [productionDarkroom, setProductionDarkroom] = useState<ProductionDarkroomPayload | null>(null);
  const [productionDarkroomLoading, setProductionDarkroomLoading] = useState(false);
  const [darkroomSourceMode, setDarkroomSourceMode] = useState(false);
  const [xmpTestDownloading, setXmpTestDownloading] = useState(false);
  const [learningDecision, setLearningDecision] = useState<ProductionLearningDecision | null>(null);
  const [retrainingStatus, setRetrainingStatus] = useState<RetrainingStatus | null>(null);
  const [retrainingLoading, setRetrainingLoading] = useState(false);
  const [profileOverview, setProfileOverview] = useState<PhotographerProfileOverview | null>(null);
  const [profileOverviewLoading, setProfileOverviewLoading] = useState(false);
  const [feedbackSavedText, setFeedbackSavedText] = useState("");
  const [feedbackLockedVerdict, setFeedbackLockedVerdict] = useState<FeedbackVerdict | null>(null);
  const [correctionMode, setCorrectionMode] = useState(false);
  const [correctionRendering, setCorrectionRendering] = useState(false);
  const [correctionPreviewUrl, setCorrectionPreviewUrl] = useState<string | null>(null);
  const [correctionRecipe, setCorrectionRecipe] = useState<CanonicalRecipe | null>(null);
  const correctionRequestRef = useRef(0);

  const [eventName, setEventName] = useState("");
  const [eventType, setEventType] = useState("חתונה");
  const [customEventType, setCustomEventType] = useState("");
  const [eventDate, setEventDate] = useState(() => localTodayForInput());
  const [styleNote, setStyleNote] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [creatingEvent, setCreatingEvent] = useState(false);
  const [uploadProgressText, setUploadProgressText] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [profileSaved, setProfileSaved] = useState(false);
  const [compare, setCompare] = useState(50);
  const [photoZoom, setPhotoZoom] = useState(1);
  const [photoPan, setPhotoPan] = useState({ x: 0, y: 0 });
  const [photoPanning, setPhotoPanning] = useState(false);
  const panStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const compareFrameRef = useRef<HTMLDivElement | null>(null);

  const loadAuthSession = async () => {
    const token = window.localStorage.getItem("prographer_session");
    if (!token) { setAuthReady(true); return; }
    try {
      const response = await apiFetch("/api/auth/me");
      const data = await response.json();
      setAuthUser(data.user); setOnboarding(data.onboarding);
    } catch {
      window.localStorage.removeItem("prographer_session"); setAuthUser(null);
    } finally { setAuthReady(true); }
  };

  const submitAuth = async () => {
    setAuthMessage(""); setAuthSubmitting(true);
    try {
      const endpoint = authMode === "register" ? "/api/auth/register" : "/api/auth/login";
      const payload = authMode === "register"
        ? { email: authEmail, password: authPassword, display_name: authDisplayName, studio_name: authStudioName }
        : { email: authEmail, password: authPassword };
      const response = await publicApiFetch(endpoint, { method: "POST", body: JSON.stringify(payload) });
      const data = await response.json();
      window.localStorage.setItem("prographer_session", data.token);
      if (authMode === "register") {
        // A brand-new account must never inherit a Lightroom import pointer
        // left in this browser by a previous installation/account.
        window.localStorage.removeItem("prographer_active_ai_profile_import");
        setLightroomActiveProfileId("");
        setLightroomDatasetBuild(null);
        setLightroomDatasetAudit(null);
        setLightroomVisionJob(null);
        setLightroomTrainingRun(null);
        setRecipeV2Report(null);
        setTrainingV2Run(null);
      }
      setAuthUser(data.user); setAuthPassword("");
      if (data.user.onboarding_completed) {
        const me = await apiFetch("/api/auth/me"); const meData = await me.json(); setOnboarding(meData.onboarding);
      } else setOnboardingStep(1);
    } catch (error) { setAuthMessage(error instanceof Error ? error.message : "ההתחברות נכשלה"); }
    finally { setAuthSubmitting(false); }
  };

  const toggleOnboardingValue = (key: "specialties" | "style_words" | "priorities", value: string) => {
    setOnboarding((current) => {
      const values = current[key];
      return { ...current, [key]: values.includes(value) ? values.filter((item) => item !== value) : [...values, value] };
    });
  };

  const saveOnboarding = async () => {
    if (!authUser) return;
    setOnboardingSaving(true); setAuthMessage("");
    try {
      const response = await apiFetch("/api/auth/onboarding", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...onboarding, completed: true }) });
      const data = await response.json();
      setOnboarding(data.onboarding); setAuthUser({ ...authUser, onboarding_completed: true });
      setSuccessMessage("הפרופיל הראשוני נשמר. מעכשיו ProGrapher ממשיך ללמוד מכל החלטה.");
    } catch (error) { setAuthMessage(error instanceof Error ? error.message : "שמירת ההיכרות נכשלה"); }
    finally { setOnboardingSaving(false); }
  };

  const logout = async () => {
    try { await apiFetch("/api/auth/logout", { method: "POST" }); } catch {}
    window.localStorage.removeItem("prographer_session"); setAuthUser(null); setEvents([]); setGallery(null); setSelectedPhoto(null); setStyleDna(null); setStats(null); setView("dashboard");
  };

  const analyzeLightroomCatalog = async (path?: string) => {
    const catalogPath = (path || lightroomManualPath).trim();
    if (!catalogPath) {
      setEngineError("יש לבחור קטלוג Lightroom");
      return;
    }

    setLightroomAnalyzeLoading(true);
    setEngineError("");
    setLightroomSelectedCollections([]);

    try {
      const response = await apiFetch("/api/lightroom/catalogs/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: catalogPath }),
      });
      const data = (await response.json()) as LightroomCatalogAnalysis;
      setLightroomAnalysis(data);
      setLightroomManualPath(data.catalog.path);
      setLightroomProfileName(
        data.catalog.name.replace(/\.lrcat$/i, "") || "הפרופיל המקצועי שלי"
      );

      const autoSelectedId = data.style_discovery?.auto_selected_id;
      const recommended = (data.training_groups || []).filter((group) => group.recommended);
      if (autoSelectedId) {
        setLightroomSelectedCollections([autoSelectedId]);
      } else if (recommended.length === 1 && (data.training_groups || []).length === 1) {
        setLightroomSelectedCollections([recommended[0].id]);
      }
    } catch (error) {
      setLightroomAnalysis(null);
      setEngineError(error instanceof Error ? error.message : "ניתוח Lightroom נכשל");
    } finally {
      setLightroomAnalyzeLoading(false);
    }
  };

  const scanLightroomCatalogs = async () => {
    setLightroomScanLoading(true);
    setEngineError("");
    setSuccessMessage("");
    setLightroomAnalysis(null);
    setLightroomCatalogs([]);

    try {
      const response = await apiFetch("/api/lightroom/catalogs/scan");
      const data = await response.json();
      const catalogs = (data.catalogs || []) as LightroomCatalogCard[];
      setLightroomCatalogs(catalogs);

      if (catalogs.length === 1) {
        await analyzeLightroomCatalog(catalogs[0].path);
      } else if (!catalogs.length) {
        setSuccessMessage("לא מצאנו קטלוג אוטומטית. אפשר לבחור קובץ .lrcat לפי הנתיב שלו.");
      }
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "חיבור Lightroom נכשל");
    } finally {
      setLightroomScanLoading(false);
    }
  };

  const toggleLightroomCollection = (id: string) => {
    const singleSelection = lightroomAnalysis?.style_discovery?.selection_mode === "single";
    setLightroomSelectedCollections((current) => {
      if (singleSelection) {
        return current.includes(id) ? [] : [id];
      }
      return current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id];
    });
  };

  const loadLightroomDatasetBuild = async (profileId: string, quiet = false) => {
    if (!profileId) return;
    try {
      const response = await apiFetch(`/api/lightroom/profile-imports/${profileId}/dataset-build`);
      const data = await response.json();
      setLightroomDatasetBuild(data.dataset_build || null);
      setLightroomDatasetAudit(null);
      setLightroomActiveProfileId(profileId);
    } catch (error) {
      if (!quiet) {
        setEngineError(error instanceof Error ? error.message : "לא הצלחנו לקרוא את מצב בניית ה-Dataset");
      }
    }
  };

  const loadLightroomDatasetAudit = async (profileId: string, quiet = false) => {
    if (!profileId) return;
    try {
      const response = await apiFetch(`/api/lightroom/profile-imports/${profileId}/dataset-audit`);
      const data = await response.json();
      setLightroomDatasetAudit(data.dataset_audit || null);
    } catch (error) {
      if (!quiet) {
        setEngineError(error instanceof Error ? error.message : "לא הצלחנו לקרוא את בדיקת התקינות");
      }
    }
  };

  const rerunLightroomDatasetAudit = async () => {
    if (!lightroomActiveProfileId) return;
    try {
      const response = await apiFetch(`/api/lightroom/profile-imports/${lightroomActiveProfileId}/dataset-audit/rebuild`, {
        method: "POST",
      });
      const data = await response.json();
      setLightroomDatasetAudit(data.dataset_audit || null);
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "הפעלת בדיקת התקינות מחדש נכשלה");
    }
  };

  const loadLightroomVisionJob = async (profileId: string, quiet = false) => {
    if (!profileId) return;
    try {
      const response = await apiFetch(`/api/lightroom/profile-imports/${profileId}/vision`);
      const data = await response.json();
      setLightroomVisionJob(data.vision_job || null);
    } catch (error) {
      if (!quiet) setEngineError(error instanceof Error ? error.message : "לא הצלחנו לקרוא את מצב ניתוח ה-Vision");
    }
  };

  const rebuildLightroomVisionJob = async () => {
    if (!lightroomActiveProfileId) return;
    try {
      const response = await apiFetch(`/api/lightroom/profile-imports/${lightroomActiveProfileId}/vision/rebuild`, {
        method: "POST",
      });
      const data = await response.json();
      setLightroomVisionJob(data.vision_job || null);
      setLightroomTrainingRun(null);
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "הפעלת ניתוח Vision מחדש נכשלה");
    }
  };

  const loadLightroomTrainingRun = async (profileId: string, quiet = false) => {
    if (!profileId) return;
    try {
      const response = await apiFetch(`/api/lightroom/profile-imports/${profileId}/training`);
      const data = await response.json();
      setLightroomTrainingRun(data.training_run || null);
    } catch (error) {
      if (!quiet) setEngineError(error instanceof Error ? error.message : "לא הצלחנו לקרוא את מצב האימון");
    }
  };

  const loadLightroomEvaluation = async (profileId: string, refresh = false, quiet = false) => {
    if (!profileId) return;
    setLightroomEvaluationLoading(true);
    try {
      const response = await apiFetch(
        `/api/lightroom/profile-imports/${profileId}/evaluation${refresh ? "?refresh=true" : ""}`
      );
      const data = await response.json();
      const evaluation = (data.evaluation || null) as LightroomEvaluation | null;
      setLightroomEvaluation(evaluation);
      if (evaluation) {
        const initial = evaluation.worst_samples?.[0] || evaluation.representative_samples?.[0] || evaluation.best_samples?.[0];
        if (initial) setEvaluationSelectedSampleId(initial.sample_id);
      }
    } catch (error) {
      if (!quiet) setEngineError(error instanceof Error ? error.message : "Evaluation נכשל");
    } finally {
      setLightroomEvaluationLoading(false);
    }
  };

  const loadRecipeV2 = async (profileId: string, refresh = false, quiet = false) => {
    if (!profileId) return;
    setRecipeV2Loading(true);
    try {
      const response = await apiFetch(
        `/api/lightroom/profile-imports/${profileId}/recipe-v2${refresh ? "?refresh=true" : ""}`
      );
      const data = await response.json();
      setRecipeV2Report((data.report || null) as RecipeV2Report | null);
    } catch (error) {
      if (!quiet) setEngineError(error instanceof Error ? error.message : "Recipe Intelligence V2 נכשל");
    } finally {
      setRecipeV2Loading(false);
    }
  };

  const loadTrainingV2 = async (profileId: string, quiet = false) => {
    if (!profileId) return;
    try {
      const response = await apiFetch(`/api/lightroom/profile-imports/${profileId}/training-v2`);
      const data = await response.json();
      setTrainingV2Run((data.training_run || null) as TrainingV2Run | null);
    } catch (error) {
      if (!quiet) setEngineError(error instanceof Error ? error.message : "לא הצלחנו לקרוא את אימון V2");
    }
  };

  const startTrainingV2 = async () => {
    if (!lightroomActiveProfileId || !recipeV2Report) return;
    setTrainingV2Starting(true);
    setEngineError("");
    try {
      const response = await apiFetch(`/api/lightroom/profile-imports/${lightroomActiveProfileId}/training-v2/start`, {
        method: "POST",
      });
      const data = await response.json();
      setTrainingV2Run((data.training_run || null) as TrainingV2Run | null);
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "התחלת Context Model V2 נכשלה");
    } finally {
      setTrainingV2Starting(false);
    }
  };

  const startLightroomTraining = async () => {
    if (!lightroomActiveProfileId || lightroomVisionJob?.status !== "completed") return;
    setLightroomTrainingStarting(true);
    setEngineError("");
    try {
      const response = await apiFetch(`/api/lightroom/profile-imports/${lightroomActiveProfileId}/training/start`, {
        method: "POST",
      });
      const data = await response.json();
      setLightroomTrainingRun(data.training_run || null);
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "התחלת האימון נכשלה");
    } finally {
      setLightroomTrainingStarting(false);
    }
  };

  const saveLightroomProfileDraft = async () => {
    if (!lightroomAnalysis) return;
    setLightroomDraftSaving(true);
    setEngineError("");

    try {
      const response = await apiFetch("/api/lightroom/profile-imports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_name: lightroomProfileName.trim() || "הפרופיל המקצועי שלי",
          catalog_path: lightroomAnalysis.catalog.path,
          selected_collections: lightroomSelectedCollections,
          analysis: lightroomAnalysis,
        }),
      });
      const data = await response.json();
      setLightroomActiveProfileId(data.id || "");
      setLightroomDatasetBuild(data.dataset_build || null);
      if (typeof window !== "undefined" && data.id) {
        window.localStorage.setItem("prographer_active_ai_profile_import", data.id);
      }
      setSuccessMessage("");
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "שמירת פרופיל Lightroom נכשלה");
    } finally {
      setLightroomDraftSaving(false);
    }
  };

  const refreshBackend = async (showError = true) => {
    setEngineError("");
    try {
      const health = await apiFetch("/api/health");
      await health.json();
      setEngineOnline(true);

      setLoadingData(true);
      const [eventsRes, statsRes, systemRes, styleDnaRes] = await Promise.all([
        apiFetch("/api/events"),
        apiFetch("/api/stats"),
        apiFetch("/api/system"),
        apiFetch("/api/style/dna"),
      ]);

      setEvents(await eventsRes.json());
      setStats(await statsRes.json());
      setSystem(await systemRes.json());
      setStyleDna(await styleDnaRes.json());
    } catch (error) {
      setEngineOnline(false);
      if (showError) {
        setEngineError(
          error instanceof Error ? error.message : "לא ניתן להתחבר למנוע המקומי"
        );
      }
    } finally {
      setLoadingData(false);
    }
  };

  useEffect(() => { loadAuthSession(); }, []);

  useEffect(() => {
    if (!authReady || !authUser?.onboarding_completed) return;
    refreshBackend(true);
    const timer = window.setInterval(() => refreshBackend(false), 15000);
    return () => window.clearInterval(timer);
  }, [authReady, authUser?.id, authUser?.onboarding_completed]);

  useEffect(() => {
    if (!successMessage) return;
    const timer = window.setTimeout(() => setSuccessMessage(""), 4200);
    return () => window.clearTimeout(timer);
  }, [successMessage]);

  useEffect(() => {
    if (!["style", "style-setup", "diagnostics"].includes(view) || !engineOnline) return;
    loadRetrainingStatus(true);
    if (view === "style") {
      loadPhotographerProfileOverview(true);
    }
  }, [view, engineOnline]);

  useEffect(() => {
    if (
      !["style", "diagnostics"].includes(view) ||
      !retrainingStatus?.latest_run ||
      !["queued", "running"].includes(retrainingStatus.latest_run.status)
    ) {
      return;
    }

    const timer = window.setInterval(async () => {
      await loadRetrainingStatus(true);
      if (view === "style") {
        await loadPhotographerProfileOverview(true);
      }
    }, 1600);

    return () => window.clearInterval(timer);
  }, [view, retrainingStatus?.latest_run?.id, retrainingStatus?.latest_run?.status]);

  useEffect(() => {
    if (!engineError) return;
    const timer = window.setTimeout(() => setEngineError(""), 5200);
    return () => window.clearTimeout(timer);
  }, [engineError]);


  useEffect(() => {
    if (!selectedEventId || !eventInference?.job) return;
    if (!["queued", "running"].includes(eventInference.job.status)) return;

    const timer = window.setInterval(async () => {
      const status = await loadEventInferenceStatus(selectedEventId, true);
      if (
        status?.job &&
        !["queued", "running"].includes(status.job.status)
      ) {
        try {
          const galleryRes = await apiFetch(`/api/events/${selectedEventId}/gallery`);
          setGallery(await galleryRes.json());
          await loadEventCompletionStatus(selectedEventId, true);
        } catch {
          // The status itself is more important; gallery can refresh on next open.
        }
      }
    }, 1500);

    return () => window.clearInterval(timer);
  }, [selectedEventId, eventInference?.job?.id, eventInference?.job?.status]);


  useEffect(() => {
    if (!authUser || lightroomActiveProfileId) return;
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem("prographer_active_ai_profile_import") || "";
    if (saved) loadLightroomDatasetBuild(saved, true);
  }, [authUser, lightroomActiveProfileId]);

  useEffect(() => {
    if (!lightroomActiveProfileId || !lightroomDatasetBuild) return;
    if (["completed", "failed"].includes(lightroomDatasetBuild.status)) return;
    const timer = window.setInterval(() => {
      loadLightroomDatasetBuild(lightroomActiveProfileId, true);
    }, 1200);
    return () => window.clearInterval(timer);
  }, [lightroomActiveProfileId, lightroomDatasetBuild?.status]);


  useEffect(() => {
    if (!lightroomActiveProfileId || lightroomDatasetBuild?.status !== "completed") return;
    loadLightroomDatasetAudit(lightroomActiveProfileId, true);
  }, [lightroomActiveProfileId, lightroomDatasetBuild?.status]);

  useEffect(() => {
    if (!lightroomActiveProfileId || !lightroomDatasetAudit) return;
    if (["completed", "failed"].includes(lightroomDatasetAudit.status)) return;
    const timer = window.setInterval(() => {
      loadLightroomDatasetAudit(lightroomActiveProfileId, true);
    }, 1200);
    return () => window.clearInterval(timer);
  }, [lightroomActiveProfileId, lightroomDatasetAudit?.status]);

  useEffect(() => {
    if (!lightroomActiveProfileId) return;
    if (lightroomDatasetAudit?.status !== "completed" || !lightroomDatasetAudit.result?.passed) return;
    loadLightroomVisionJob(lightroomActiveProfileId, true);
  }, [lightroomActiveProfileId, lightroomDatasetAudit?.status, lightroomDatasetAudit?.result?.passed]);

  useEffect(() => {
    if (!lightroomActiveProfileId || !lightroomVisionJob) return;
    if (["completed", "failed"].includes(lightroomVisionJob.status)) return;
    const timer = window.setInterval(() => {
      loadLightroomVisionJob(lightroomActiveProfileId, true);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [lightroomActiveProfileId, lightroomVisionJob?.status]);

  useEffect(() => {
    if (!lightroomActiveProfileId || lightroomVisionJob?.status !== "completed") return;
    loadLightroomTrainingRun(lightroomActiveProfileId, true);
  }, [lightroomActiveProfileId, lightroomVisionJob?.status]);

  useEffect(() => {
    if (!lightroomActiveProfileId || !lightroomTrainingRun) return;
    if (["completed", "failed"].includes(lightroomTrainingRun.status)) return;
    const timer = window.setInterval(() => {
      loadLightroomTrainingRun(lightroomActiveProfileId, true);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [lightroomActiveProfileId, lightroomTrainingRun?.status]);


  useEffect(() => {
    if (!lightroomActiveProfileId || lightroomTrainingRun?.status !== "completed") return;
    loadLightroomEvaluation(lightroomActiveProfileId, false, true);
  }, [lightroomActiveProfileId, lightroomTrainingRun?.status]);


  useEffect(() => {
    if (!lightroomActiveProfileId || lightroomTrainingRun?.status !== "completed") return;
    loadRecipeV2(lightroomActiveProfileId, false, true);
    loadTrainingV2(lightroomActiveProfileId, true);
  }, [lightroomActiveProfileId, lightroomTrainingRun?.status]);

  useEffect(() => {
    if (!lightroomActiveProfileId || !trainingV2Run) return;
    if (["completed", "failed"].includes(trainingV2Run.status)) return;
    const timer = window.setInterval(() => {
      loadTrainingV2(lightroomActiveProfileId, true);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [lightroomActiveProfileId, trainingV2Run?.status]);


  useEffect(() => { setPhotoZoom(1); setPhotoPan({ x: 0, y: 0 }); setPhotoPanning(false); }, [selectedPhoto?.id]);


  const resetPhotoViewport = () => {
    setPhotoZoom(1);
    setPhotoPan({ x: 0, y: 0 });
  };

  const adjustPhotoZoom = (nextZoom: number) => {
    const clamped = Math.max(1, Math.min(4, nextZoom));
    setPhotoZoom(clamped);
    if (clamped === 1) setPhotoPan({ x: 0, y: 0 });
  };

  const handlePhotoZoomClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.closest(".compareHandle")) return;
    if (photoZoom > 1 || photoPanning) return;

    const rect = event.currentTarget.getBoundingClientRect();
    const offsetX = event.clientX - (rect.left + rect.width / 2);
    const offsetY = event.clientY - (rect.top + rect.height / 2);
    const nextZoom = 2;

    setPhotoPan({
      x: -offsetX * nextZoom,
      y: -offsetY * nextZoom,
    });
    setPhotoZoom(nextZoom);
  };

  const startPhotoPan = (event: React.PointerEvent<HTMLDivElement>) => {
    if (photoZoom <= 1) return;
    const target = event.target as HTMLElement;
    if (target.closest(".compareHandle")) return;

    event.currentTarget.setPointerCapture(event.pointerId);
    panStartRef.current = {
      x: event.clientX,
      y: event.clientY,
      panX: photoPan.x,
      panY: photoPan.y,
    };
    setPhotoPanning(true);
  };

  const movePhotoPan = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!photoPanning || photoZoom <= 1) return;
    const start = panStartRef.current;
    setPhotoPan({
      x: start.panX + event.clientX - start.x,
      y: start.panY + event.clientY - start.y,
    });
  };

  const endPhotoPan = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setPhotoPanning(false);
  };

  const photoTransformStyle: React.CSSProperties = {
    transform: `translate3d(${photoPan.x}px, ${photoPan.y}px, 0) scale(${photoZoom})`,
    transformOrigin: "center center",
  };

  const photoWidth =
    selectedPhoto?.width || selectedPhoto?.metadata?.width || 4;
  const photoHeight =
    selectedPhoto?.height || selectedPhoto?.metadata?.height || 3;
  const photoIsPortrait = photoHeight > photoWidth;

  const photoStageStyle: React.CSSProperties = {
    aspectRatio: `${photoWidth} / ${photoHeight}`,
    ...(photoIsPortrait
      ? { height: "100%", width: "auto" }
      : { width: "100%", height: "auto" }),
  };

  const updateCompareFromClientX = (clientX: number) => {
    const frame = compareFrameRef.current;
    if (!frame) return;

    const rect = frame.getBoundingClientRect();
    const x = clientX - rect.left;
    const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
    setCompare(percentage);
  };

  const loadEventCompletionStatus = async (eventId: string, quiet = false) => {
    try {
      const res = await apiFetch(`/api/events/${eventId}/completion/status`);
      const data = (await res.json()) as EventCompletionStatus;
      setEventCompletion(data);
      return data;
    } catch (error) {
      if (!quiet) {
        setEngineError(
          error instanceof Error ? error.message : "לא הצלחנו לטעון את מצב סיום האירוע"
        );
      }
      return null;
    }
  };

  const approveRemainingEventEdits = async () => {
    if (!selectedEventId) return;
    setEventCompletionLoading(true);
    setEngineError("");
    try {
      const res = await apiFetch(
        `/api/events/${selectedEventId}/completion/approve-remaining`,
        { method: "POST" }
      );
      const data = await res.json();
      setEventCompletion({
        ...(data.status as EventCompletionStatus),
        ok: true,
        export_format: "prographer-lightroom-xmp-export-v1",
      });
      const galleryRes = await apiFetch(`/api/events/${selectedEventId}/gallery`);
      setGallery(await galleryRes.json());
      await refreshBackend();
    } catch (error) {
      setEngineError(
        error instanceof Error ? error.message : "אישור העריכות שנותרו נכשל"
      );
    } finally {
      setEventCompletionLoading(false);
    }
  };

  const completeAndExportEvent = async () => {
    if (!selectedEventId) return;
    setEventCompletionLoading(true);
    setEngineError("");
    try {
      const res = await apiFetch(
        `/api/events/${selectedEventId}/completion/export`,
        { method: "POST" }
      );
      const data = await res.json();
      const status = data.status as EventCompletionStatus;
      setEventCompletion({
        ...status,
        ok: true,
        export_format: "prographer-lightroom-xmp-export-v1",
      });
      const galleryRes = await apiFetch(`/api/events/${selectedEventId}/gallery`);
      setGallery(await galleryRes.json());
      await refreshBackend();
    } catch (error) {
      setEngineError(
        error instanceof Error ? error.message : "סיום האירוע ויצירת XMP נכשלו"
      );
    } finally {
      setEventCompletionLoading(false);
    }
  };

  const downloadEventExport = async () => {
    const exportItem = eventCompletion?.latest_export;
    if (!selectedEventId || !exportItem) return;

    setEventCompletionLoading(true);
    setEngineError("");
    try {
      const res = await apiFetch(
        `/api/events/${selectedEventId}/completion/export/${exportItem.id}/download`
      );
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = exportItem.file_name || "ProGrapher_Lightroom_XMP.zip";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setEngineError(
        error instanceof Error ? error.message : "הורדת קובץ ה-XMP נכשלה"
      );
    } finally {
      setEventCompletionLoading(false);
    }
  };

  const loadEventInferenceStatus = async (eventId: string, quiet = false) => {
    try {
      const res = await apiFetch(`/api/events/${eventId}/ai/inference/status`);
      const data = await res.json();
      setEventInference(data as EventInferenceStatus);
      return data as EventInferenceStatus;
    } catch (error) {
      if (!quiet) {
        setEngineError(
          error instanceof Error ? error.message : "לא הצלחנו לקרוא את מצב עריכת ה-AI"
        );
      }
      return null;
    }
  };

  const startEventInference = async () => {
    if (!selectedEventId) return;
    setEventInferenceStarting(true);
    setEngineError("");
    try {
      const res = await apiFetch(`/api/events/${selectedEventId}/ai/inference/start`, {
        method: "POST",
      });
      await res.json();
      await loadEventInferenceStatus(selectedEventId, true);
    } catch (error) {
      setEngineError(
        error instanceof Error ? error.message : "הפעלת עריכת ה-AI לאירוע נכשלה"
      );
    } finally {
      setEventInferenceStarting(false);
    }
  };

  const openEvent = async (eventId: string) => {
    setSelectedEventId(eventId);
    setSelectedPhoto(null);
    setAnalysisResult(null);
    setAnalysisCreatedAt(null);
    setFeedbackLockedVerdict(null);
    setFeedbackSavedText("");
    setCorrectionMode(false);
    setCorrectionPreviewUrl(null);
    setCorrectionRecipe(null);
    setGalleryLoading(true);
    setEventInference(null);
    setEventCompletion(null);
    setEngineError("");
    setView("event-detail");

    try {
      const [res] = await Promise.all([
        apiFetch(`/api/events/${eventId}/gallery`),
        loadEventInferenceStatus(eventId, true),
        loadEventCompletionStatus(eventId, true),
      ]);
      setGallery(await res.json());
    } catch (error) {
      setGallery(null);
      setEngineError(error instanceof Error ? error.message : "טעינת האירוע נכשלה");
    } finally {
      setGalleryLoading(false);
    }
  };

  const loadPhotographerProfileOverview = async (quiet = false) => {
    setProfileOverviewLoading(true);
    try {
      const res = await apiFetch("/api/ai/profile/overview");
      const data = (await res.json()) as PhotographerProfileOverview;
      setProfileOverview(data);
      return data;
    } catch (error) {
      if (!quiet) {
        setEngineError(
          error instanceof Error ? error.message : "לא הצלחנו לטעון את פרופיל ה-AI"
        );
      }
      return null;
    } finally {
      setProfileOverviewLoading(false);
    }
  };

  const finalizeInitialAiProfile = async () => {
    if (!lightroomActiveProfileId) return;
    setLightroomTrainingStarting(true);
    setEngineError("");
    try {
      const res = await apiFetch(
        `/api/lightroom/profile-imports/${lightroomActiveProfileId}/production-profile/register`,
        { method: "POST" }
      );
      const data = await res.json();
      const registryId = data?.registry?.id;
      if (registryId) {
        await apiFetch(`/api/ai/profiles/${registryId}/make-default`, {
          method: "POST",
        });
      }
      await loadRetrainingStatus(true);
      await loadPhotographerProfileOverview(true);
      await refreshBackend(false);
      setSuccessMessage("פרופיל ה-AI שלך מוכן ופעיל.");
      setView("style");
    } catch (error) {
      setEngineError(
        error instanceof Error ? error.message : "הפעלת פרופיל ה-AI נכשלה"
      );
    } finally {
      setLightroomTrainingStarting(false);
    }
  };

  const resetStyleSetup = () => {
    setLightroomAnalysis(null);
    setLightroomCatalogs([]);
    setLightroomSelectedCollections([]);
    setLightroomDatasetBuild(null);
    setLightroomDatasetAudit(null);
    setLightroomVisionJob(null);
    setLightroomTrainingRun(null);
    setRecipeV2Report(null);
    setTrainingV2Run(null);
    setLightroomActiveProfileId("");
    setLightroomManualPath("");
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("prographer_active_ai_profile_import");
    }
  };

  const beginInitialStyleSetup = async () => {
    // This is the FIRST step of connecting Lightroom, so it must work even
    // when the account has never imported a catalog before.
    resetStyleSetup();
    setSuccessMessage("");
    setEngineError("");
    setView("style-setup");

    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    // One click should actually begin the onboarding flow, not wait for a
    // previous Lightroom connection that cannot exist on a fresh account.
    await scanLightroomCatalogs();
  };

  const loadRetrainingStatus = async (quiet = false) => {
    try {
      const res = await apiFetch("/api/ai/retraining/status");
      const data = (await res.json()) as RetrainingStatus;
      setRetrainingStatus(data);
      return data;
    } catch (error) {
      if (!quiet) {
        setEngineError(
          error instanceof Error ? error.message : "לא הצלחנו לטעון את מצב שיפור הפרופיל"
        );
      }
      return null;
    }
  };

  const startAdaptiveRetraining = async () => {
    setRetrainingLoading(true);
    setEngineError("");
    try {
      const res = await apiFetch("/api/ai/retraining/start", {
        method: "POST",
      });
      await res.json();
      await loadRetrainingStatus(true);
    } catch (error) {
      setEngineError(
        error instanceof Error ? error.message : "יצירת גרסת Profile משופרת נכשלה"
      );
    } finally {
      setRetrainingLoading(false);
    }
  };

  const activateCandidateProfile = async () => {
    const registryId =
      profileOverview?.active_profile?.registry_id ||
      retrainingStatus?.active_profile?.registry_id;
    const candidateId =
      profileOverview?.candidate?.id ||
      retrainingStatus?.candidate_version?.id;
    if (!registryId || !candidateId) return;

    setRetrainingLoading(true);
    setEngineError("");
    try {
      await apiFetch(
        `/api/ai/profiles/${registryId}/versions/${candidateId}/activate`,
        { method: "POST" }
      );
      await loadRetrainingStatus(true);
      await loadPhotographerProfileOverview(true);
      await refreshBackend();
    } catch (error) {
      setEngineError(
        error instanceof Error ? error.message : "הפעלת גרסת ה-Profile החדשה נכשלה"
      );
    } finally {
      setRetrainingLoading(false);
    }
  };

  const prepareProductionDarkroom = async (photoId: string) => {
    setProductionDarkroomLoading(true);
    setEngineError("");
    try {
      const res = await apiFetch(`/api/photos/${photoId}/ai/darkroom/prepare`, {
        method: "POST",
      });
      const data = (await res.json()) as ProductionDarkroomPayload;
      setProductionDarkroom(data);
      setCorrectionMode(false);
      setCorrectionPreviewUrl(null);
      setCorrectionRecipe(null);
      return data;
    } catch (error) {
      setProductionDarkroom(null);
      setEngineError(
        error instanceof Error
          ? error.message
          : "הכנת עריכת ProGrapher לתמונה נכשלה"
      );
      return null;
    } finally {
      setProductionDarkroomLoading(false);
    }
  };

  const loadLatestAnalysis = async (photoId: string) => {
    const res = await apiFetch(`/api/photos/${photoId}/analysis-latest`);
    const data = await res.json();
    if (data?.exists && data.analysis) {
      setAnalysisResult(data.analysis as AnalysisPayload);
      setAnalysisCreatedAt(data.created_at || null);
    } else {
      setAnalysisResult(null);
      setAnalysisCreatedAt(null);
    }
  };

  const openPhoto = async (
    photo: ApiPhoto,
    returnView: "event-detail" | "training-review" = "event-detail"
  ) => {
    setPhotoReturnView(returnView);
    setSelectedPhoto(photo);
    setAnalysisResult(null);
    setAnalysisCreatedAt(null);
    setProductionDarkroom(null);
    setDarkroomSourceMode(false);
    setLearningDecision(photo.latest_ai_learning_decision || null);
    setFeedbackSavedText("");
    setFeedbackLockedVerdict(photo.latest_feedback?.verdict || null);
    setCorrectionMode(false);
    setCorrectionPreviewUrl(null);
    setCorrectionRecipe(null);
    setPhotoLoading(true);
    setView("photo-detail");

    try {
      const res = await apiFetch(`/api/photos/${photo.id}/details`);
      const full = await res.json();
      setSelectedPhoto(full);
      setLearningDecision(full.latest_ai_learning_decision || null);
      // Production learning is separate from legacy Style DNA feedback.
      setFeedbackLockedVerdict(null);
      const prepared = await prepareProductionDarkroom(photo.id);
      if (prepared) {
        const refreshed = await apiFetch(`/api/photos/${photo.id}/details`);
        const refreshedData = await refreshed.json();
        setSelectedPhoto(refreshedData);
        setLearningDecision(refreshedData.latest_ai_learning_decision || null);
        if (refreshedData.latest_ai_learning_decision?.photographer_recipe) {
          setCorrectionRecipe({
            ...refreshedData.latest_ai_learning_decision.photographer_recipe,
          });
        }
      }
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "טעינת התמונה נכשלה");
    } finally {
      setPhotoLoading(false);
    }
  };

  const loadTrainingReview = async (
    eventId: string,
    count: number = trainingReviewCount
  ) => {
    setSelectedEventId(eventId);
    setTrainingReviewLoading(true);
    setEngineError("");
    setView("training-review");

    try {
      const res = await apiFetch(
        `/api/events/${eventId}/brain/training-review?count=${count}`
      );
      setTrainingReview(await res.json());
    } catch (error) {
      setTrainingReview(null);
      setEngineError(
        error instanceof Error
          ? error.message
          : "בחירת תמונות האימון נכשלה"
      );
    } finally {
      setTrainingReviewLoading(false);
    }
  };

  const changeTrainingReviewCount = async (count: number) => {
    setTrainingReviewCount(count);
    if (selectedEventId) {
      await loadTrainingReview(selectedEventId, count);
    }
  };

  const openTrainingPhoto = async (item: TrainingReviewItem) => {
    const galleryPhoto = gallery?.photos.find(
      (photo) => photo.id === item.photo_id
    );

    if (galleryPhoto) {
      await openPhoto(galleryPhoto, "training-review");
      return;
    }

    setPhotoLoading(true);
    setEngineError("");
    try {
      const res = await apiFetch(`/api/photos/${item.photo_id}/details`);
      const full = await res.json();
      await openPhoto(full, "training-review");
    } catch (error) {
      setEngineError(
        error instanceof Error ? error.message : "טעינת התמונה נכשלה"
      );
    } finally {
      setPhotoLoading(false);
    }
  };

  const returnToPhotoSource = async () => {
    if (photoReturnView === "training-review" && selectedEventId) {
      await loadTrainingReview(selectedEventId, trainingReviewCount);
      return;
    }

    if (selectedEventId) {
      await openEvent(selectedEventId);
    }
  };

  const runPhotoAnalysis = async () => {
    if (!selectedPhoto) return;
    setAnalysisLoading(true);
    setEngineError("");
    try {
      const res = await apiFetch(`/api/photos/${selectedPhoto.id}/analyze`, { method: "POST" });
      const data = await res.json();
      setAnalysisResult({
        metrics: data.metrics,
        assessment: data.assessment,
        recipe: data.recipe,
        base_recipe: data.base_recipe,
        style_dna: data.style_dna,
      });
      setAnalysisCreatedAt(data.created_at || null);
      const detailsRes = await apiFetch(`/api/photos/${selectedPhoto.id}/details`);
      setSelectedPhoto(await detailsRes.json());
      if (selectedEventId) {
        const galleryRes = await apiFetch(`/api/events/${selectedEventId}/gallery`);
        setGallery(await galleryRes.json());
      }
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "הניתוח נכשל");
    } finally {
      setAnalysisLoading(false);
    }
  };

  const runRecipeRender = async () => {
    if (!selectedPhoto) return;
    setRenderLoading(true);
    setEngineError("");
    try {
      const res = await apiFetch(`/api/photos/${selectedPhoto.id}/render-preview`, { method: "POST" });
      const data = await res.json();
      setSelectedPhoto(data.photo);
      setSuccessMessage("נוצר preview ערוך ונשמר בתיקיית edited.");
      if (selectedEventId) {
        const galleryRes = await apiFetch(`/api/events/${selectedEventId}/gallery`);
        setGallery(await galleryRes.json());
      }
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "ה־Render נכשל");
    } finally {
      setRenderLoading(false);
    }
  };

  const saveProductionDecision = async (
    verdict: "approved" | "corrected",
    photographerRecipe?: CanonicalRecipe
  ) => {
    if (!selectedPhoto || !productionDarkroom?.prediction?.recipe) return null;

    setFeedbackLoading(true);
    setEngineError("");

    try {
      const res = await apiFetch(`/api/photos/${selectedPhoto.id}/ai/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          verdict,
          photographer_recipe:
            verdict === "corrected" ? photographerRecipe || correctionRecipe : undefined,
          note:
            verdict === "approved"
              ? "Production AI edit approved without changes"
              : "Production AI edit corrected by photographer",
        }),
      });
      const data = await res.json();
      const decision = data.decision as ProductionLearningDecision;

      setLearningDecision(decision);
      setFeedbackSavedText(
        verdict === "approved"
          ? "העריכה אושרה ונשמרה ללמידה"
          : "התיקון נשמר ונכנס ללמידה"
      );
      setCorrectionMode(false);
      setCorrectionPreviewUrl(null);
      setCorrectionRecipe({ ...decision.photographer_recipe });

      const detailsRes = await apiFetch(`/api/photos/${selectedPhoto.id}/details`);
      const updated = await detailsRes.json();
      setSelectedPhoto(updated);
      setLearningDecision(updated.latest_ai_learning_decision || decision);

      if (selectedEventId) {
        const galleryRes = await apiFetch(`/api/events/${selectedEventId}/gallery`);
        setGallery(await galleryRes.json());
        await loadEventCompletionStatus(selectedEventId, true);
      }

      await loadPhotographerProfileOverview(true);
      await refreshBackend();
      return decision;
    } catch (error) {
      setEngineError(
        error instanceof Error ? error.message : "שמירת ההחלטה ללמידה נכשלה"
      );
      return null;
    } finally {
      setFeedbackLoading(false);
    }
  };

  const approveProductionEdit = async () => {
    await saveProductionDecision("approved");
  };

  const startCorrectionMode = () => {
    if (!productionDarkroom?.prediction?.recipe) return;
    setDarkroomSourceMode(false);
    const baseRecipe =
      learningDecision?.photographer_recipe ||
      productionDarkroom.prediction.recipe;
    setCorrectionRecipe({ ...baseRecipe });
    setCorrectionPreviewUrl(
      learningDecision?.final_render_url ||
      productionDarkroom.render?.rendered_url ||
      null
    );
    setCorrectionMode(true);
    setFeedbackSavedText("");
  };

  const cancelCorrectionMode = () => {
    setCorrectionMode(false);
    setCorrectionPreviewUrl(null);
    setCorrectionRecipe(null);
  };

  const updateCorrectionValue = (
    key: keyof CanonicalRecipe,
    value: number
  ) => {
    setCorrectionRecipe((current) =>
      current ? { ...current, [key]: value } : current
    );
  };

  const commitCorrection = async () => {
    if (!selectedPhoto || !productionDarkroom || !correctionRecipe) return;
    await saveProductionDecision("corrected", correctionRecipe);
  };

  const refreshPhotoMetadata = async () => {
    if (!selectedPhoto) return;
    setPhotoLoading(true);
    try {
      const res = await apiFetch(`/api/photos/${selectedPhoto.id}/refresh-metadata`, { method: "POST" });
      const updated = await res.json();
      setSelectedPhoto(updated);
      if (selectedEventId) {
        const galleryRes = await apiFetch(`/api/events/${selectedEventId}/gallery`);
        setGallery(await galleryRes.json());
      }
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "רענון נתוני התמונה נכשל");
    } finally {
      setPhotoLoading(false);
    }
  };

  useEffect(() => {
    if (!correctionMode || !selectedPhoto || !correctionRecipe) return;

    const timer = window.setTimeout(async () => {
      const requestId = ++correctionRequestRef.current;
      setCorrectionRendering(true);

      try {
        const res = await apiFetch(
          `/api/photos/${selectedPhoto.id}/ai/darkroom/preview`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              recipe: correctionRecipe,
            }),
          }
        );
        const data = await res.json();

        if (requestId === correctionRequestRef.current) {
          setCorrectionPreviewUrl(
            `${data.rendered_url}?v=${encodeURIComponent(data.created_at)}`
          );
        }
      } catch (error) {
        if (requestId === correctionRequestRef.current) {
          setEngineError(
            error instanceof Error ? error.message : "Preview התיקון נכשל"
          );
        }
      } finally {
        if (requestId === correctionRequestRef.current) {
          setCorrectionRendering(false);
        }
      }
    }, 450);

    return () => window.clearTimeout(timer);
  }, [correctionMode, correctionRecipe, selectedPhoto?.id]);

  const RAW_EVENT_EXTENSIONS = new Set([
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".raf", ".pef",
  ]);

  const isSupportedEventRaw = (file: File) => {
    const dot = file.name.lastIndexOf(".");
    const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
    return RAW_EVENT_EXTENSIONS.has(ext);
  };

  const addFiles = (incoming: FileList | File[]) => {
    const next = Array.from(incoming);
    const rejected = next.filter((file) => !isSupportedEventRaw(file));
    if (rejected.length) {
      setEngineError(
        `ProGrapher עורך כרגע RAW בלבד. לא נוספו ${rejected.length} קבצים שאינם RAW.`
      );
    }
    const rawOnly = next.filter(isSupportedEventRaw);
    setFiles((current) => {
      const existing = new Set(current.map((f) => `${f.name}-${f.size}-${f.lastModified}`));
      const unique = rawOnly.filter((f) => !existing.has(`${f.name}-${f.size}-${f.lastModified}`));
      return [...current, ...unique];
    });
  };

  const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(e.target.files);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files) addFiles(e.dataTransfer.files);
  };

  const createRealEvent = async () => {
    if (!engineOnline) {
      setEngineError("המנוע המקומי לא מחובר. הפעל את start_backend.bat ונסה שוב.");
      return;
    }
    if (!eventName.trim()) {
      setEngineError("יש להזין שם לאירוע.");
      return;
    }

    const unsupportedFiles = files.filter((file) => !isSupportedEventRaw(file));
    if (unsupportedFiles.length) {
      setEngineError("אירוע Production חייב להכיל RAW בלבד. הסר JPG/PNG/WEBP ונסה שוב.");
      return;
    }

    const resolvedEventType =
      eventType === "אחר" ? customEventType.trim() : eventType;

    if (!resolvedEventType) {
      setEngineError("יש לרשום איזה סוג אירוע זה.");
      return;
    }

    setCreatingEvent(true);
    setEngineError("");
    setSuccessMessage("");

    try {
      setUploadProgressText("יוצר אירוע במחשב המקומי...");

      const eventRes = await apiFetch("/api/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: eventName.trim(),
          event_type: resolvedEventType,
          event_date: eventDate || null,
          style_note: styleNote || null,
        }),
      });

      const created = await eventRes.json();

      if (files.length > 0) {
        setUploadProgressText(`מעלה ${files.length} תמונות ישירות למחשב...`);
        const form = new FormData();
        files.forEach((file) => form.append("files", file));
        const uploadRes = await apiFetch(`/api/events/${created.id}/photos`, { method: "POST", body: form });
        const uploaded = await uploadRes.json();
        setSuccessMessage(`האירוע "${created.name}" נוצר בהצלחה ו־${uploaded.count} תמונות נשמרו במחשב שלך.`);
      } else {
        setSuccessMessage(`האירוע "${created.name}" נוצר בהצלחה במחשב שלך.`);
      }

      setEventName("");
      setEventType("חתונה");
      setCustomEventType("");
      setEventDate(localTodayForInput());
      setStyleNote("");
      setFiles([]);
      setUploadProgressText("");
      await refreshBackend();

      window.setTimeout(() => openEvent(created.id), 700);
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "יצירת האירוע נכשלה");
      setUploadProgressText("");
    } finally {
      setCreatingEvent(false);
    }
  };

  const latestEvent = events[0];

  const requestDeleteEvent = (event: ApiEvent) => {
    setDeleteTarget(event);
    setKeepLearningOnDelete(true);
    setEngineError("");
  };

  const confirmDeleteEvent = async () => {
    if (!deleteTarget) return;

    setDeletingEvent(true);
    setEngineError("");

    try {
      const res = await apiFetch(
        `/api/events/${deleteTarget.id}?keep_learning=${keepLearningOnDelete ? "true" : "false"}`,
        { method: "DELETE" }
      );
      const result = await res.json();

      setDeleteTarget(null);
      setGallery(null);
      setSelectedPhoto(null);
      setTrainingReview(null);

      if (selectedEventId === result.event_id) {
        setSelectedEventId(null);
        setView("events");
      }

      await refreshBackend();

      setSuccessMessage(
        keepLearningOnDelete
          ? `האירוע נמחק. נשמרו ${result.learning_samples_preserved ?? 0} אותות למידה של סגנון הצלם.`
          : "האירוע וכל המידע שלו נמחקו."
      );
    } catch (error) {
      setEngineError(
        error instanceof Error ? error.message : "מחיקת האירוע נכשלה"
      );
    } finally {
      setDeletingEvent(false);
    }
  };

  const navigate = (target: ViewId) => {
    setSuccessMessage("");
    setView(target);
  };

  const updateDarkroomValue = (
    key: keyof CanonicalRecipe,
    value: number
  ) => {
    setDarkroomSourceMode(false);
    const aiRecipe = productionDarkroom?.prediction?.recipe;
    if (!aiRecipe) return;

    if (!correctionMode || !correctionRecipe) {
      setCorrectionRecipe({ ...aiRecipe, [key]: value });
      setCorrectionPreviewUrl(productionDarkroom?.render?.rendered_url || null);
      setCorrectionMode(true);
      setFeedbackSavedText("");
      return;
    }

    updateCorrectionValue(key, value);
  };

  const resetDarkroomToAi = () => {
    const aiRecipe = productionDarkroom?.prediction?.recipe;
    if (!aiRecipe) return;
    setDarkroomSourceMode(false);
    setCorrectionRecipe({ ...aiRecipe });
    setCorrectionPreviewUrl(productionDarkroom?.render?.rendered_url || null);
    setCorrectionMode(Boolean(learningDecision));
    setFeedbackSavedText("");
  };

  const resetDarkroomToSource = () => {
    setDarkroomSourceMode(true);
    setCorrectionMode(false);
    setCorrectionRecipe(null);
    setCorrectionPreviewUrl(null);
    setFeedbackSavedText("מציג את ה-RAW המקורי ללא Recipe של ProGrapher");
  };

  const downloadAiXmpTest = async () => {
    if (!selectedPhoto) return;
    setXmpTestDownloading(true);
    setEngineError("");
    try {
      const res = await apiFetch(`/api/photos/${selectedPhoto.id}/ai/xmp-test`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      const base = selectedPhoto.original_name.replace(/\.[^.]+$/, "");
      link.download = `${base}.xmp`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setEngineError(error instanceof Error ? error.message : "הורדת XMP לבדיקה נכשלה");
    } finally {
      setXmpTestDownloading(false);
    }
  };

  const trainingCurrentIndex =
    photoReturnView === "training-review" && trainingReview && selectedPhoto
      ? trainingReview.items.findIndex((item) => item.photo_id === selectedPhoto.id)
      : -1;

  const trainingPreviousItem =
    trainingCurrentIndex > 0 && trainingReview
      ? trainingReview.items[trainingCurrentIndex - 1]
      : null;

  const trainingNextItem =
    trainingCurrentIndex >= 0 && trainingReview && trainingCurrentIndex < trainingReview.items.length - 1
      ? trainingReview.items[trainingCurrentIndex + 1]
      : null;

  const activeEditedUrl = darkroomSourceMode
    ? selectedPhoto?.preview_url || null
    : correctionPreviewUrl ||
      learningDecision?.final_render_url ||
      productionDarkroom?.render?.rendered_url ||
      selectedPhoto?.latest_ai_preview_render?.rendered_url ||
      null;
  const hasRender = Boolean(activeEditedUrl);
  const productionRecipe = productionDarkroom?.prediction?.recipe || null;
  const photographerFinalRecipe =
    learningDecision?.photographer_recipe || productionRecipe;

  const styleNarrative = buildStyleNarrative(styleDna, onboarding);

  if (!authReady) return <main className="authLoadingScreen"><div className="authLoadingMark"><img src="/prographer-mark.png" alt="ProGrapher" /></div><span>מכין את סביבת העבודה...</span></main>;

  if (!authUser) return (
    <main className="authShell">
      <section className="authVisualPanel">
        <div className="authBrand"><img src="/prographer-logo.png" alt="ProGrapher" /></div>
        <div className="authVisualContent"><span className="authKicker">AI EDITING PROFILE</span><h1>העריכה שלך.<br />המוח של ProGrapher.</h1><p>מערכת עריכה שלומדת את ההחלטות שלך — תאורה, צבע, קונטרסט וגישה לכל סוג אירוע.</p><div className="authColorRibbon" aria-hidden="true"><i/><i/><i/><i/></div></div>
        <div className="authVisualFooter"><span>RAW</span><span>STYLE DNA</span><span>LOCAL GPU</span></div>
      </section>
      <section className="authFormPanel"><div className="authCard">
        <div className="authCardHead"><span>{authMode === "login" ? "ברוך שובך" : "יצירת פרופיל חדש"}</span><h2>{authMode === "login" ? "כניסה ל־ProGrapher" : "בוא נבנה את העורך שלך"}</h2><p>{authMode === "login" ? "המשך בדיוק מאיפה שעצרת." : "אחרי ההרשמה נכיר את הדרך שבה אתה מצלם ועורך."}</p></div>
        {authMode === "register" && <div className="authFieldGrid"><label>השם שלך<input value={authDisplayName} onChange={(e)=>setAuthDisplayName(e.target.value)} placeholder="לדוגמה: מתן" /></label><label>שם הסטודיו<input value={authStudioName} onChange={(e)=>setAuthStudioName(e.target.value)} placeholder="אופציונלי" /></label></div>}
        <label>אימייל<input type="email" value={authEmail} onChange={(e)=>setAuthEmail(e.target.value)} placeholder="name@studio.co.il" autoComplete="email" /></label>
        <label>סיסמה<input type="password" value={authPassword} onChange={(e)=>setAuthPassword(e.target.value)} placeholder="לפחות 8 תווים" autoComplete={authMode === "login" ? "current-password" : "new-password"} onKeyDown={(e)=>{if(e.key === "Enter") submitAuth();}} /></label>
        {authMessage && <div className="authError">{authMessage}</div>}
        <button className="authSubmit" onClick={submitAuth} disabled={authSubmitting || !authEmail.trim() || authPassword.length < 8 || (authMode === "register" && !authDisplayName.trim())}>{authSubmitting?"רק רגע...":authMode === "login"?"כניסה":"יצירת חשבון"}</button>
        <button className="authSwitch" onClick={()=>{setAuthMode(authMode === "login" ? "register" : "login");setAuthMessage("");}}>{authMode === "login"?"אין לך חשבון? צור פרופיל חדש":"כבר יש לך חשבון? התחבר"}</button>
      </div></section>
    </main>
  );

  if (!authUser.onboarding_completed) {
    const specialties=["חתונות","חינה","בר מצווה","בת מצווה","פורטרטים","אירועים עסקיים"];
    const styleWords=["נקי","טבעי","חם","קריר","חד","רך","בהיר","דרמטי","צבע עשיר","גווני עור טבעיים"];
    const priorities=["גווני עור","שמלת כלה","שמיים ו־Highlights","אור טבעי","רעש בתאורה חלשה","עקביות בין תמונות"];
    return <main className="onboardingShell"><section className="onboardingHeader"><img src="/prographer-logo.png" alt="ProGrapher"/><div><span>היכרות ראשונית</span><strong>{onboardingStep} / 4</strong></div></section><section className="onboardingCard"><div className="onboardingProgress"><i style={{width:`${onboardingStep*25}%`}}/></div>
      {onboardingStep===1&&<div className="onboardingStep"><span className="onboardingEyebrow">שלב 1 — עולם הצילום שלך</span><h1>מה אתה מצלם בדרך כלל?</h1><p>בחר כמה שרלוונטי. זה עוזר ל־ProGrapher לדעת אילו מצבים חשוב ללמוד קודם.</p><div className="choiceGrid">{specialties.map((item)=><button key={item} className={onboarding.specialties.includes(item)?"selected":""} onClick={()=>toggleOnboardingValue("specialties",item)}>{item}</button>)}</div></div>}
      {onboardingStep===2&&<div className="onboardingStep"><span className="onboardingEyebrow">שלב 2 — סביבת העריכה</span><h1>איפה אתה עורך היום?</h1><p>בהמשך נשתמש בזה כדי לייבא היסטוריית עריכה אמיתית.</p><div className="choiceGrid three">{["Lightroom Classic","Capture One","Photoshop","אחר"].map((item)=><button key={item} className={onboarding.editor_software===item?"selected":""} onClick={()=>setOnboarding({...onboarding,editor_software:item})}>{item}</button>)}</div></div>}
      {onboardingStep===3&&<div className="onboardingStep"><span className="onboardingEyebrow">שלב 3 — שפת הצבע שלך</span><h1>איך היית מתאר את הסגנון שלך?</h1><p>המנוע ישווה בהמשך בין מה שאמרת למה שאתה באמת עושה בתמונות.</p><div className="choiceGrid">{styleWords.map((item)=><button key={item} className={onboarding.style_words.includes(item)?"selected":""} onClick={()=>toggleOnboardingValue("style_words",item)}>{item}</button>)}</div></div>}
      {onboardingStep===4&&<div className="onboardingStep"><span className="onboardingEyebrow">שלב 4 — מה אסור ל־AI לפספס</span><h1>מה הכי חשוב לך בעריכה?</h1><p>אלו יהיו נקודות תשומת הלב הראשונות כשנבנה את פרופיל העריכה שלך.</p><div className="choiceGrid">{priorities.map((item)=><button key={item} className={onboarding.priorities.includes(item)?"selected":""} onClick={()=>toggleOnboardingValue("priorities",item)}>{item}</button>)}</div><label className="onboardingNotes">משהו נוסף שחשוב שנדע?<textarea value={onboarding.notes} onChange={(e)=>setOnboarding({...onboarding,notes:e.target.value})} placeholder="לדוגמה: בחוץ אני אוהב אור טבעי ונקי, ברחבה צבע חי יותר..."/></label></div>}
      {authMessage&&<div className="authError">{authMessage}</div>}<div className="onboardingActions"><button className="ghost" disabled={onboardingStep===1||onboardingSaving} onClick={()=>setOnboardingStep((step)=>Math.max(1,step-1))}>חזרה</button>{onboardingStep<4?<button className="authSubmit compact" onClick={()=>setOnboardingStep((step)=>Math.min(4,step+1))}>המשך</button>:<button className="authSubmit compact" onClick={saveOnboarding} disabled={onboardingSaving}>{onboardingSaving?"שומר...":"התחל לעבוד עם ProGrapher"}</button>}</div>
    </section></main>;
  }

  return (
    <div className={`app ${sidebarCollapsed ? "sidebarIsCollapsed" : ""}`}>
      <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
        <div className="sidebarTop">
          <button className="compactBrand" onClick={() => navigate("dashboard")} aria-label="ProGrapher">
            <img src="/prographer-logo.png" alt="ProGrapher" />
          </button>

          <button
            className="sidebarFoldButton"
            onClick={() => setSidebarCollapsed((value) => !value)}
            aria-label={sidebarCollapsed ? "פתח תפריט" : "קפל תפריט"}
            title={sidebarCollapsed ? "פתח תפריט" : "קפל תפריט"}
          >
            <span className={`sidebarFoldGlyph ${sidebarCollapsed ? "open" : "close"}`} aria-hidden="true">
              <i />
              <i />
            </span>
          </button>
        </div>

        <nav className="nav">
          {MENU.map(([id, label]) => (
            <button
              key={id}
              onClick={() => navigate(id)}
              className={view === id || (id === "events" && (view === "event-detail" || view === "training-review" || view === "photo-detail")) ? "active" : ""}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className="workstation">
          <div className="workstationTitle">
            <span className={`statusDot ${engineOnline ? "online" : engineOnline === false ? "offline" : ""}`} />
            {engineOnline === null ? "בודק את תחנת העבודה" : engineOnline ? "תחנת העבודה מחוברת" : "תחנת העבודה מנותקת"}
          </div>
          <div>Backend: {API_BASE}</div>
          <div>RAW: {system?.raw_support ? "פעיל" : engineOnline ? "לא פעיל" : "—"}</div>
          <div>EXIF: {system?.exif_support ? "פעיל" : engineOnline ? "לא פעיל" : "—"}</div>
          <div>GPU: {system?.gpu?.available ? system.gpu.name : engineOnline ? "לא זוהה" : "—"}</div>
          <button className="miniRefresh" onClick={() => refreshBackend(true)}>בדיקה מחדש</button>
        </div>
      </aside>

      <section className={`content ${sidebarCollapsed ? "sidebarCollapsedContent" : ""}`}>
        <header className="headerShell">
          <div className="topbar">
            <button className="topLogo" onClick={() => navigate("dashboard")} aria-label="ProGrapher">
              <img src="/prographer-logo.png" alt="ProGrapher" />
            </button>

            <div className="topActions">
              <div className={`engineChip ${engineOnline ? "connected" : engineOnline === false ? "disconnected" : ""}`}>
                <span />
                {engineOnline === null ? "בודק מנוע" : engineOnline ? "המנוע מחובר" : "המנוע מנותק"}
              </div>

              <div className="profileCluster">
                <button className="profileChip" onClick={() => navigate("profile")}><span className="avatar">{authUser.display_name.slice(0,1)}</span><span className="profileChipText"><strong>{authUser.display_name}</strong><small>{authUser.studio_name || "פרופיל הצלם"}</small></span></button>
                <button className="logoutMini" onClick={logout} title="התנתקות">יציאה</button>
              </div>

              <button className="primary desktopNewEvent" onClick={() => navigate("new-event")}>יצירת אירוע חדש</button>
            </div>
          </div>

          <nav className="subnav" aria-label="ניווט ראשי">
            {MENU.map(([id, label]) => (
              <button
                key={id}
                onClick={() => navigate(id)}
                className={view === id || (id === "events" && (view === "event-detail" || view === "training-review" || view === "photo-detail")) ? "active" : ""}
              >
                {label}
              </button>
            ))}
          </nav>
        </header>

        <main>
          {view === "dashboard" && (
            <>
              <section className="hero heroNoLogo">
                <div className="heroText">
                  <div className="eyebrow">סביבת העבודה הראשית</div>
                  <h1>ברוך הבא ל־ProGrapher</h1>
                  <p>ProGrapher כבר משתמש בהחלטות ובתיקונים שלך כדי להתאים מתכוני עריכה חדשים לסגנון שלך.</p>
                  <div className="heroActions">
                    <button className="primary" onClick={() => navigate("events")}>פתיחת האירועים</button>
                    <button className="ghost" onClick={() => navigate("new-event")}>אירוע חדש</button>
                  </div>
                </div>
              </section>

              <section className="statsGrid">
                <Stat label="אירועים" value={stats ? String(stats.events) : "—"} />
                <Stat label="תמונות במחשב" value={stats ? String(stats.photos) : "—"} />
                <Stat label="קבלה ללא תיקון" value={stats?.acceptance_rate != null ? `${stats.acceptance_rate}%` : "—"} />
                <Stat label="זוגות סגנון" value={stats ? String(stats.style_pairs) : "—"} />
              </section>

              <section className="twoColumns">
                <div className="panel">
                  <div className="panelTitle">האירוע האחרון</div>
                  {latestEvent ? (
                    <button className="eventCard clickableEvent" onClick={() => openEvent(latestEvent.id)}>
                      <div className="eventHead">
                        <div>
                          <strong>{latestEvent.name}</strong>
                          <span>{latestEvent.event_type} · {latestEvent.photo_count ?? 0} תמונות</span>
                        </div>
                        <em>{latestEvent.status}</em>
                      </div>
                      <div className="openHint">פתיחת האירוע ←</div>
                    </button>
                  ) : (
                    <div className="emptyState">עדיין אין אירועים.</div>
                  )}
                </div>

                <div className="panel">
                  <div className="panelTitle">תחנת העבודה</div>
                  <div className="miniGrid">
                    <MiniStat label="Backend" value={engineOnline ? "מחובר" : "מנותק"} />
                    <MiniStat label="RAW" value={system?.raw_support ? "פעיל" : "—"} />
                    <MiniStat label="EXIF" value={system?.exif_support ? "פעיל" : "—"} />
                    <MiniStat label="GPU" value={system?.gpu?.available ? system.gpu.name || "זוהה" : "—"} />
                  </div>
                </div>
              </section>
            </>
          )}

          {view === "events" && (
            <section className="eventsStudio">
              <div className="eventsStudioHero">
                <div className="eventsStudioIntro">
                  <span className="eventsStudioKicker">ספריית העבודה שלך</span>
                  <h2>אירועים</h2>
                  <p>כל אירוע הוא סביבת עבודה נפרדת — תמונות, ניתוח, עריכה ולמידת סגנון.</p>
                </div>

                <div className="eventsStudioActions">
                  <div className="eventsCountBadge">
                    <strong>{events.length}</strong>
                    <span>אירועים</span>
                  </div>
                  <button className="chromaPrimary" onClick={() => navigate("new-event")}>אירוע חדש</button>
                </div>
              </div>

              {loadingData ? (
                <div className="eventsEmptyState">טוען את ספריית האירועים...</div>
              ) : events.length === 0 ? (
                <div className="eventsEmptyState">אין עדיין אירועים. צור את האירוע הראשון שלך.</div>
              ) : (
                <div className="eventsCardGrid chromaEventGrid">
                  {events.map((event) => (
                    <article className={`eventTileWrap chromaEventCard ${eventToneClass(event.event_type)}`} key={event.id}>
                      <button
                        className="eventTile chromaEventTile"
                        onClick={() => openEvent(event.id)}
                      >
                        <div className="eventSpectralArt" aria-hidden="true">
                          <span className="spectralBlob one" />
                          <span className="spectralBlob two" />
                          <span className="spectralBlob three" />
                          <span className="spectralGrid" />
                        </div>

                        <div className="eventTileTop chromaEventTop">
                          <span className="eventTileType">{event.event_type}</span>
                          <em>{event.status}</em>
                        </div>

                        <div className="eventTileBody chromaEventBody">
                          <strong>{event.name}</strong>
                          <div className="eventTileMeta chromaEventMeta">
                            <span><i className="metaDot photos" />{event.photo_count ?? 0} תמונות</span>
                            <span><i className="metaDot date" />{formatEventDate(event.event_date)}</span>
                          </div>
                        </div>

                        <div className="eventTileOpen chromaEventOpen">
                          <span>כניסה לסביבת העבודה</span>
                          <i className="eventTileArrow" aria-hidden="true">←</i>
                        </div>
                      </button>

                      <button
                        className="eventTileDelete chromaEventDelete"
                        onClick={() => requestDeleteEvent(event)}
                        title="מחיקת אירוע"
                        aria-label={`מחיקת ${event.name}`}
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5" />
                        </svg>
                        <span>מחיקה</span>
                      </button>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {view === "event-detail" && (
            <>
              <div className="breadcrumbBar">
                <button onClick={() => navigate("events")}>אירועים</button>
                <span>›</span>
                <strong>{gallery?.event.name || "אירוע"}</strong>
              </div>

              {galleryLoading ? <div className="panel emptyState">טוען את האירוע...</div> : !gallery ? (
                <div className="panel emptyState">לא ניתן לטעון את האירוע.</div>
              ) : (
                <>
                  <section className="eventDetailHero panel">
                    <div>
                      <div className="eyebrow">{gallery.event.event_type}</div>
                      <h2>{gallery.event.name}</h2>
                      <p>{gallery.event.style_note || "אין הערת סגנון לאירוע הזה."}</p>
                    </div>
                    <div className="eventDetailActions">
                      <span className="statusBadge">{gallery.event.status}</span>
                      <button
                        className="eventAiButton"
                        onClick={startEventInference}
                        disabled={
                          eventInferenceStarting ||
                          !!(eventInference?.job && ["queued", "running"].includes(eventInference.job.status)) ||
                          !eventInference?.active_profile
                        }
                      >
                        {eventInferenceStarting
                          ? "מפעיל ProGrapher..."
                          : eventInference?.job && ["queued", "running"].includes(eventInference.job.status)
                            ? `עורך ${eventInference.job.processed_photos}/${eventInference.job.total_photos}`
                            : eventInference?.coverage.complete
                              ? "עריכת AI מוכנה"
                              : eventInference?.active_profile
                                ? "ערוך את האירוע עם ProGrapher"
                                : "אין פרופיל AI פעיל"}
                      </button>
                      <button className="ghost" onClick={() => loadTrainingReview(gallery.event.id, trainingReviewCount)}>
                        בחירת תמונות לאימון
                      </button>
                      <button className="ghost dangerButton" onClick={() => requestDeleteEvent(gallery.event)}>
                        מחיקת אירוע
                      </button>
                      <button className="primary" onClick={() => navigate("new-event")}>אירוע חדש</button>
                    </div>
                  </section>

                  <section className="eventStats">
                    <SmallStat label="תמונות" value={String(gallery.summary.photo_count)} />
                    <SmallStat label="RAW" value={String(gallery.summary.raw_count)} />
                    <SmallStat label="Previews" value={String(gallery.summary.preview_count)} />
                    <SmallStat label="תחזיות AI" value={String(gallery.summary.ai_prediction_count ?? 0)} />
                    <SmallStat label="גודל מקור" value={formatBytes(gallery.summary.total_bytes)} />
                  </section>

                  <section className={`eventAiProgress panel ${eventInference?.coverage.complete ? "complete" : ""}`}>
                    <div className="eventAiProgressHead">
                      <div>
                        <span>ACTIVE AI PROFILE</span>
                        <strong>
                          {eventInference?.active_profile
                            ? `${eventInference.active_profile.name || "הסגנון שלי"} · V${eventInference.active_profile.version_number}`
                            : "עדיין אין פרופיל AI פעיל"}
                        </strong>
                        <p>
                          {eventInference?.active_profile
                            ? "זה הפרופיל היחיד שבו ProGrapher משתמש כרגע לעריכת האירוע."
                            : "יש להשלים את בניית הסגנון לפני שניתן לערוך אירועים אוטומטית."}
                        </p>
                      </div>
                      {eventInference?.active_profile && (
                        <div className="eventAiCoverage">
                          <strong>{Math.round(eventInference.coverage.progress_percent)}%</strong>
                          <span>
                            {eventInference.coverage.predicted_photos}/{eventInference.coverage.eligible_photos} תמונות
                          </span>
                        </div>
                      )}
                    </div>

                    {eventInference?.active_profile && (
                      <>
                        <div className="eventAiTrack">
                          <i style={{ width: `${Math.max(0, Math.min(100, eventInference.coverage.progress_percent))}%` }} />
                        </div>
                        <div className="eventAiProgressFoot">
                          <span>
                            {eventInference?.job && ["queued", "running"].includes(eventInference.job.status)
                              ? eventInference.job.details?.current_photo
                                ? `מעבד עכשיו: ${eventInference.job.details.current_photo}`
                                : "ProGrapher מנתח את האירוע..."
                              : eventInference.coverage.complete
                                ? "התחזיות נשמרו ומוכנות לחיבור למעבדת העריכה."
                                : "מוכן להתחיל עריכת AI של כל התמונות באירוע."}
                          </span>
                          {!!eventInference?.job?.failed_photos && (
                            <em>{eventInference.job.failed_photos} תמונות נכשלו</em>
                          )}
                        </div>
                      </>
                    )}
                  </section>

                  <section className={`eventCompletionCard panel ${eventCompletion?.completed ? "completed" : ""}`}>
                    <div className="eventCompletionHead">
                      <div>
                        <span>EVENT COMPLETION</span>
                        <h3>
                          {eventCompletion?.completed
                            ? "האירוע הושלם"
                            : "סיום האירוע וייצוא ל-Lightroom"}
                        </h3>
                        <p>
                          {eventCompletion?.completed
                            ? "העריכות הסופיות נשמרו. ניתן להוריד Sidecar XMP תואם Lightroom."
                            : "בדוק את התמונות שדורשות תיקון, אשר את השאר וסיים את האירוע."}
                        </p>
                      </div>
                      <div className="eventCompletionCount">
                        <strong>
                          {eventCompletion?.decided_photos ?? 0}/{eventCompletion?.total_photos ?? gallery.summary.photo_count}
                        </strong>
                        <span>החלטות סופיות</span>
                      </div>
                    </div>

                    <div className="eventCompletionStats">
                      <div>
                        <span>אושרו</span>
                        <strong>{eventCompletion?.approved_photos ?? 0}</strong>
                      </div>
                      <div>
                        <span>תוקנו ידנית</span>
                        <strong>{eventCompletion?.corrected_photos ?? 0}</strong>
                      </div>
                      <div>
                        <span>נותרו לבדיקה</span>
                        <strong>{eventCompletion?.remaining_decisions ?? gallery.summary.photo_count}</strong>
                      </div>
                      <div>
                        <span>Lightroom Export</span>
                        <strong>
                          {eventCompletion?.export_up_to_date
                            ? "מוכן"
                            : eventCompletion?.latest_export
                              ? "דורש עדכון"
                              : "—"}
                        </strong>
                      </div>
                    </div>

                    <div className="eventCompletionActions">
                      {(eventCompletion?.remaining_decisions || 0) > 0 && (
                        <button
                          className="ghost"
                          onClick={approveRemainingEventEdits}
                          disabled={
                            eventCompletionLoading ||
                            (eventCompletion?.remaining_predictions || 0) > 0
                          }
                        >
                          {eventCompletionLoading
                            ? "מבצע..."
                            : (eventCompletion?.remaining_predictions || 0) > 0
                              ? "השלם קודם את עריכת ה-AI"
                              : `אשר את ${eventCompletion?.remaining_decisions || 0} העריכות שנותרו`}
                        </button>
                      )}

                      {eventCompletion?.ready_to_complete && !eventCompletion?.export_up_to_date && (
                        <button
                          className="primary eventCompletePrimary"
                          onClick={completeAndExportEvent}
                          disabled={eventCompletionLoading}
                        >
                          {eventCompletionLoading
                            ? "מייצא..."
                            : eventCompletion?.latest_export
                              ? "ייצא XMP מעודכן"
                              : "סיים אירוע וייצא XMP"}
                        </button>
                      )}

                      {eventCompletion?.latest_export && eventCompletion.export_up_to_date && (
                        <button
                          className="primary eventCompletePrimary"
                          onClick={downloadEventExport}
                          disabled={eventCompletionLoading}
                        >
                          {eventCompletionLoading ? "מכין הורדה..." : "הורד XMP ל-Lightroom"}
                        </button>
                      )}
                    </div>

                    <div className="eventCompletionFoot">
                      <span>
                        RAW המקורי לא משתנה. ProGrapher מייצא Sidecar XMP בשם זהה לכל קובץ RAW.
                      </span>
                      {eventCompletion?.latest_export && (
                        <small>
                          {eventCompletion.latest_export.file_name} · {eventCompletion.latest_export.photo_count} תמונות
                        </small>
                      )}
                    </div>
                  </section>

                  <section className="galleryHeader">
                    <div>
                      <h3>גלריית האירוע</h3>
                      <p>אלו ה־Previews שנוצרו מהקבצים המקוריים ששמורים במחשב.</p>
                    </div>
                  </section>

                  {gallery.photos.length === 0 ? <div className="panel emptyState">אין תמונות באירוע.</div> : (
                    <section className="photoGrid">
                      {gallery.photos.map((photo) => (
                        <button className="photoCard" key={photo.id} onClick={() => openPhoto(photo)}>
                          <div className="photoThumb">
                            {photo.preview_url ? <LocalImage url={photo.preview_url} alt={photo.original_name} /> : <div className="noPreview">אין Preview</div>}
                            <span className="fileTypeBadge">{photo.extension || photo.metadata?.file_type || "IMG"}</span>
                            {photo.edited_url && <span className="editedBadge">ערוך</span>}
                            {photo.latest_ai_prediction && <span className="aiReadyBadge">AI מוכן</span>}
                          </div>
                          <div className="photoCardBody">
                            <strong title={photo.original_name}>{photo.original_name}</strong>
                            <span>{cameraLabel(photo.metadata)}</span>
                            <div className="photoMetaLine">
                              <small>{photo.metadata?.iso ? `ISO ${photo.metadata.iso}` : "ISO —"}</small>
                              <small>{photo.metadata?.aperture || "צמצם —"}</small>
                              <small>{photo.metadata?.shutter_speed || "תריס —"}</small>
                            </div>
                          </div>
                        </button>
                      ))}
                    </section>
                  )}
                </>
              )}
            </>
          )}

          {view === "training-review" && (
            <>
              <div className="breadcrumbBar">
                <button onClick={() => navigate("events")}>אירועים</button>
                <span>›</span>
                <button onClick={() => selectedEventId && openEvent(selectedEventId)}>
                  {trainingReview?.event.name || gallery?.event.name || "אירוע"}
                </button>
                <span>›</span>
                <strong>בחירת תמונות לאימון</strong>
              </div>

              {trainingReviewLoading ? (
                <div className="panel emptyState">בוחר את התמונות המגוונות ביותר לאימון...</div>
              ) : !trainingReview ? (
                <div className="panel emptyState">
                  לא ניתן לבנות כרגע סט אימון. ודא שהאירוע עבר ניתוח מוח מלא.
                </div>
              ) : (
                <>
                  <section className="trainingHero panel">
                    <div>
                      <div className="eyebrow">TRAINING REVIEW</div>
                      <h2>סט האימון החכם של {trainingReview.event.name}</h2>
                      <p>
                        ProGrapher בחר תמונות שמכסות כמה שיותר סצנות, תאורות ומראה חזותי שונה.
                        המטרה היא שתערוך פחות תמונות — אבל שכל אחת מהן תלמד את המוח משהו חדש.
                      </p>
                    </div>

                    <div className="trainingCountPicker">
                      <span>כמות לבחירה</span>
                      <div>
                        {[32, 48, 64].map((count) => (
                          <button
                            key={count}
                            className={trainingReviewCount === count ? "active" : ""}
                            onClick={() => changeTrainingReviewCount(count)}
                          >
                            {count}
                          </button>
                        ))}
                      </div>
                    </div>
                  </section>

                  <section className="trainingStats">
                    <SmallStat label="נותחו ע״י המוח" value={String(trainingReview.analyzed_photos)} />
                    <SmallStat label="נבחרו לאימון" value={String(trainingReview.selected_count)} />
                    <SmallStat label="כבר הושלמו" value={String(trainingReview.reviewed_count)} />
                    <SmallStat label="נשארו לעריכה" value={String(trainingReview.remaining_count)} />
                  </section>

                  <section className="trainingProgress panel">
                    <div>
                      <strong>התקדמות Ground Truth</strong>
                      <span>
                        {trainingReview.reviewed_count} מתוך {trainingReview.selected_count} תמונות כבר קיבלו החלטת צלם
                      </span>
                    </div>
                    <div className="trainingProgressTrack">
                      <i
                        style={{
                          width: `${
                            trainingReview.selected_count
                              ? (trainingReview.reviewed_count / trainingReview.selected_count) * 100
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </section>

                  <section className="galleryHeader trainingGalleryHeader">
                    <div>
                      <h3>התמונות שנבחרו</h3>
                      <p>
                        {trainingReview.semantic_combinations} שילובי סצנה ותאורה שונים נכללו בבחירה.
                        פתח תמונה, צור עריכה, ואשר או תקן אותה.
                      </p>
                    </div>
                    <button
                      className="ghost"
                      onClick={() => selectedEventId && loadTrainingReview(selectedEventId, trainingReviewCount)}
                    >
                      חשב מחדש
                    </button>
                  </section>

                  <section className="trainingPhotoGrid">
                    {trainingReview.items.map((item) => (
                      <article
                        className={`trainingPhotoCard ${item.reviewed ? "completed" : ""}`}
                        key={item.photo_id}
                      >
                        <button
                          className="trainingPhotoImage"
                          onClick={() => openTrainingPhoto(item)}
                        >
                          {item.preview_url ? (
                            <LocalImage url={item.preview_url} alt={item.original_name} />
                          ) : (
                            <div className="noPreview">אין Preview</div>
                          )}

                          <span className="trainingRank">#{item.rank}</span>
                          <span className={`trainingState ${item.reviewed ? "done" : ""}`}>
                            {item.reviewed ? "הושלם" : "ממתין לעריכה"}
                          </span>
                        </button>

                        <div className="trainingPhotoBody">
                          <strong title={item.original_name}>{item.original_name}</strong>

                          <div className="trainingTags">
                            {item.scene?.label_he && <span>{item.scene.label_he}</span>}
                            {item.lighting?.label_he && <span>{item.lighting.label_he}</span>}
                            {item.people?.label_he && <span>{item.people.label_he}</span>}
                          </div>

                          <p>{item.selection_reason}</p>

                          <div className="trainingPhotoFooter">
                            <small>
                              שונות חזותית {Math.round(item.visual_distance_percent)}%
                            </small>
                            <button onClick={() => openTrainingPhoto(item)}>
                              {item.reviewed ? "פתיחה מחדש" : "פתח לעריכה"}
                            </button>
                          </div>
                        </div>
                      </article>
                    ))}
                  </section>
                </>
              )}
            </>
          )}

          {view === "photo-detail" && (
            <>
              <div className="breadcrumbBar darkroomBreadcrumb">
                <button onClick={() => navigate("events")}>אירועים</button>
                <span>›</span>
                <button onClick={returnToPhotoSource}>
                  {photoReturnView === "training-review"
                    ? "בחירת תמונות לאימון"
                    : (gallery?.event.name || "אירוע")}
                </button>
                <span>›</span>
                <strong>{selectedPhoto?.original_name || "תמונה"}</strong>
              </div>

              {photoLoading && !selectedPhoto ? (
                <div className="panel emptyState">טוען תמונה...</div>
              ) : selectedPhoto ? (
                <section className="darkroomPage">
                  <div className="darkroomTopbar">
                    <div className="darkroomFileIdentity">
                      <button className="darkroomBack" onClick={returnToPhotoSource}>←</button>
                      <div>
                        <strong>{selectedPhoto.original_name}</strong>
                        <span>
                          {cameraLabel(selectedPhoto.metadata)}
                          {selectedPhoto.metadata?.iso ? ` · ISO ${selectedPhoto.metadata.iso}` : ""}
                          {selectedPhoto.metadata?.aperture ? ` · ${selectedPhoto.metadata.aperture}` : ""}
                          {selectedPhoto.metadata?.shutter_speed ? ` · ${selectedPhoto.metadata.shutter_speed}` : ""}
                        </span>
                      </div>
                    </div>

                    <div className="darkroomTopActions">
                      {photoReturnView === "training-review" && trainingReview && (
                        <div className="trainingStepper">
                          <button
                            disabled={!trainingPreviousItem}
                            onClick={() => trainingPreviousItem && openTrainingPhoto(trainingPreviousItem)}
                          >
                            הקודם
                          </button>
                          <span>
                            {trainingCurrentIndex >= 0 ? trainingCurrentIndex + 1 : "—"} / {trainingReview.items.length}
                          </span>
                          <button
                            disabled={!trainingNextItem}
                            onClick={() => trainingNextItem && openTrainingPhoto(trainingNextItem)}
                          >
                            הבא
                          </button>
                        </div>
                      )}
                      <span className="statusBadge photoReadyBadge">{photoStatusLabel(selectedPhoto.status)}</span>
                    </div>
                  </div>

                  <div className="darkroomWorkspace">
                    <div className="darkroomCanvasColumn">
                      <div className={`darkroomCanvas ${photoPanning ? "isPanning" : ""}`}>
                        {hasRender && selectedPhoto.preview_url && activeEditedUrl ? (
                          <div className="darkroomCompareShell">
                            <div
                              ref={compareFrameRef}
                              className="darkroomCompareFrame darkroomPhotoStage"
                              style={photoStageStyle}
                              onClick={handlePhotoZoomClick}
                              onPointerDown={startPhotoPan}
                              onPointerMove={movePhotoPan}
                              onPointerUp={endPhotoPan}
                              onPointerCancel={endPhotoPan}
                              onDoubleClick={resetPhotoViewport}
                              title={photoZoom === 1 ? "לחץ על אזור בתמונה להגדלה" : "גרור כדי לנוע · לחיצה כפולה לאיפוס"}
                            >
                              <div className="darkroomZoomLayer" style={photoTransformStyle}>
                                <LocalImage
                                  className="darkroomImage"
                                  url={selectedPhoto.preview_url}
                                  alt={`${selectedPhoto.original_name} source`}
                                />
                                <div
                                  className="compareOverlay"
                                  style={{ clipPath: `inset(0 0 0 ${compare}%)` }}
                                >
                                  <LocalImage
                                    className="darkroomImage"
                                    url={activeEditedUrl}
                                    alt={`${selectedPhoto.original_name} edited`}
                                  />
                                </div>
                              </div>
                              <div className="compareLine" style={{ left: `${compare}%` }}>
                                <button
                                  type="button"
                                  className="compareHandle"
                                  onPointerDown={(e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    e.currentTarget.setPointerCapture(e.pointerId);
                                    updateCompareFromClientX(e.clientX);
                                  }}
                                  onPointerMove={(e) => {
                                    if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
                                    e.preventDefault();
                                    updateCompareFromClientX(e.clientX);
                                  }}
                                  onPointerUp={(e) => {
                                    e.preventDefault();
                                    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
                                      e.currentTarget.releasePointerCapture(e.pointerId);
                                    }
                                  }}
                                  onPointerCancel={(e) => {
                                    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
                                      e.currentTarget.releasePointerCapture(e.pointerId);
                                    }
                                  }}
                                  aria-label="גרירת ידית ההשוואה"
                                >
                                  <span className="compareHandleGlyph" aria-hidden="true">
                                    <i className="compareHandleChevron left" />
                                    <i className="compareHandleChevron right" />
                                  </span>
                                </button>
                              </div>
                              <div className="beforeBadge">ערוך</div>
                              <div className="afterBadge">מקור</div>
                            </div>
                          </div>
                        ) : selectedPhoto.preview_url ? (
                          <div
                            className="darkroomSingleStage darkroomPhotoStage"
                            style={photoStageStyle}
                            onClick={handlePhotoZoomClick}
                            onPointerDown={startPhotoPan}
                            onPointerMove={movePhotoPan}
                            onPointerUp={endPhotoPan}
                            onPointerCancel={endPhotoPan}
                            onDoubleClick={resetPhotoViewport}
                            title={photoZoom === 1 ? "לחץ על אזור בתמונה להגדלה" : "גרור כדי לנוע · לחיצה כפולה לאיפוס"}
                          >
                            <div className="darkroomZoomLayer" style={photoTransformStyle}>
                              <LocalImage
                                className="darkroomImage single"
                                url={selectedPhoto.preview_url}
                                alt={selectedPhoto.original_name}
                              />
                            </div>
                          </div>
                        ) : (
                          <div className="noPreview">אין Preview זמין</div>
                        )}
                      </div>

                      <div className="darkroomCanvasBar">
                        <div className="darkroomZoomControls"><button onClick={() => adjustPhotoZoom(photoZoom / 1.2)} disabled={photoZoom <= 1}>−</button><button className="zoomReadout" onClick={resetPhotoViewport}>{Math.round(photoZoom * 100)}%</button><button onClick={() => adjustPhotoZoom(photoZoom * 1.2)} disabled={photoZoom >= 5}>+</button></div>
                        <div className="darkroomViewModes">
                          {hasRender && (
                            <>
                              <button onClick={() => setCompare(100)}>מקור</button>
                              <button className="active" onClick={() => setCompare(50)}>מקור / ערוך</button>
                              <button onClick={() => setCompare(0)}>ערוך</button>
                            </>
                          )}
                        </div>

                        <div className="darkroomCanvasStatus">
                          {correctionRendering
                            ? "מעדכן Preview..."
                            : correctionMode
                            ? "Preview תיקון פעיל"
                            : learningDecision?.verdict === "approved"
                            ? "אושר ונשמר ללמידה"
                            : learningDecision?.verdict === "corrected"
                            ? "תיקון סופי נשמר ללמידה"
                            : hasRender
                            ? "Preview ערוך מוכן"
                            : "ממתין לעריכה"}
                        </div>
                      </div>

                      <details className="darkroomMetaStrip">
                        <summary>
                          <span>פרטי צילום וקובץ</span>
                          <small>
                            {cameraLabel(selectedPhoto.metadata)} · {resolutionLabel(selectedPhoto)} · {formatBytes(selectedPhoto.file_size || 0)}
                          </small>
                        </summary>
                        <div className="darkroomMetaGrid">
                          <div>
                            <div className="panelTitle">נתוני צילום</div>
                            <MetadataRows metadata={selectedPhoto.metadata} />
                          </div>
                          <div>
                            <div className="panelTitle">נתוני הקובץ</div>
                            <InfoRow label="סוג" value={selectedPhoto.metadata?.file_type || selectedPhoto.extension || "—"} />
                            <InfoRow label="גודל" value={formatBytes(selectedPhoto.file_size || 0)} />
                            <InfoRow label="רזולוציה" value={resolutionLabel(selectedPhoto)} />
                            <InfoRow label="RAW" value={selectedPhoto.is_raw ? "כן" : "לא"} />
                            <InfoRow label="מקור Metadata" value={selectedPhoto.metadata?.metadata_source || "—"} />
                          </div>
                        </div>
                      </details>

                      {productionDarkroom && (
                        <details className="darkroomAnalysisDetails">
                          <summary>
                            <span>פרטי עריכת ProGrapher</span>
                            <small>
                              Profile V{productionDarkroom.prediction.profile_version_number} · {productionDarkroom.recipe_contract.version}
                            </small>
                          </summary>
                          <div className="darkroomAnalysisContent productionRecipeInspector">
                            <div>
                              <span>Profile Version</span>
                              <strong>V{productionDarkroom.prediction.profile_version_number}</strong>
                            </div>
                            <div>
                              <span>Process</span>
                              <strong>{productionDarkroom.process_family === "legacy" ? "Lightroom Legacy" : productionDarkroom.process_family}</strong>
                            </div>
                            <div>
                              <span>Temperature</span>
                              <strong>Kelvin מוחלט</strong>
                            </div>
                            <div>
                              <span>Preview</span>
                              <strong>קירוב לתצוגה בלבד</strong>
                            </div>
                          </div>
                        </details>
                      )}
                    </div>

                    <aside className="darkroomControls">
                      <div className="darkroomControlsHeader">
                        <div>
                          <span>עריכה</span>
                          <strong>Basic</strong>
                        </div>
                        <div className={`liveRenderBadge ${correctionRendering ? "working" : ""}`}>
                          <span />
                          {correctionRendering ? "מעדכן" : "מוכן"}
                        </div>
                      </div>

                      {productionDarkroomLoading ? (
                        <div className="darkroomControlsBody">
                          <div className="darkroomSetupState">
                            <strong>ProGrapher מכין את העריכה</strong>
                            <p>טוען את ה-Active Profile, מחשב Recipe ומכין Preview.</p>
                          </div>
                        </div>
                      ) : !productionDarkroom || !productionRecipe ? (
                        <div className="darkroomControlsBody">
                          <div className="darkroomSetupState">
                            <strong>עריכת ה-AI עדיין לא מוכנה</strong>
                            <p>נסה להכין מחדש את התמונה בעזרת ה-Active AI Profile.</p>
                            <button
                              className="primary"
                              onClick={() => selectedPhoto && prepareProductionDarkroom(selectedPhoto.id)}
                              disabled={productionDarkroomLoading}
                            >
                              נסה שוב
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className={`darkroomControlsBody ${darkroomSourceMode ? "sourceMode" : ""}`}>
                            <div className="productionDarkroomIdentity">
                              <div>
                                <span>PROGRAPHER ACTIVE PROFILE</span>
                                <strong>
                                  {selectedPhoto.active_ai_profile?.name || "הסגנון שלי"} · V{productionDarkroom.prediction.profile_version_number}
                                </strong>
                              </div>
                              <em>RAW PREVIEW · מקורב</em>
                            </div>
                            <div className="rawPreviewSafetyNote">
                              ה-Preview נבנה מה-RAW המקורי פעם אחת. Lightroom/XMP הוא ה-render הסופי והמדויק.
                            </div>
                            {darkroomSourceMode && (
                              <div className="darkroomSourceModePanel">
                                <strong>מצב מקור — ללא עריכת ProGrapher</strong>
                                <span>הצד הערוך מציג כרגע את אותו RAW מקור. כל ה-Recipe של ה-AI מושבת לצורך השוואה.</span>
                              </div>
                            )}

                            {(productionRecipe.temperature !== undefined || productionRecipe.tint !== undefined) && (
                              <div className="darkroomControlSection">
                                <div className="darkroomSectionTitle">איזון לבן</div>
                                {productionRecipe.temperature !== undefined && (
                                  <DarkroomSlider
                                    label="טמפרטורה"
                                    track="temperature"
                                    value={correctionRecipe?.temperature ?? photographerFinalRecipe?.temperature ?? productionRecipe.temperature}
                                    aiValue={productionRecipe.temperature}
                                    min={2000}
                                    max={50000}
                                    step={50}
                                    unit="K"
                                    signed={false}
                                    showNeutral={false}
                                    onChange={(value) => updateDarkroomValue("temperature", value)}
                                  />
                                )}
                                {productionRecipe.tint !== undefined && (
                                  <DarkroomSlider
                                    label="Tint"
                                    value={correctionRecipe?.tint ?? photographerFinalRecipe?.tint ?? productionRecipe.tint}
                                    aiValue={productionRecipe.tint}
                                    min={-150}
                                    max={150}
                                    step={1}
                                    onChange={(value) => updateDarkroomValue("tint", value)}
                                  />
                                )}
                              </div>
                            )}

                            <div className="darkroomControlSection">
                              <div className="darkroomSectionTitle">גוון וטון</div>
                              {productionRecipe.exposure !== undefined && (
                                <DarkroomSlider
                                  label="חשיפה"
                                  track="exposure"
                                  value={correctionRecipe?.exposure ?? photographerFinalRecipe?.exposure ?? productionRecipe.exposure}
                                  aiValue={productionRecipe.exposure}
                                  min={-5}
                                  max={5}
                                  step={0.05}
                                  onChange={(value) => updateDarkroomValue("exposure", value)}
                                />
                              )}
                              {productionRecipe.contrast !== undefined && (
                                <DarkroomSlider
                                  label="ניגודיות"
                                  track="contrast"
                                  value={correctionRecipe?.contrast ?? photographerFinalRecipe?.contrast ?? productionRecipe.contrast}
                                  aiValue={productionRecipe.contrast}
                                  min={-100}
                                  max={100}
                                  step={1}
                                  neutralValue={productionDarkroom.process_family === "legacy" ? 25 : 0}
                                  onChange={(value) => updateDarkroomValue("contrast", value)}
                                />
                              )}
                              {productionRecipe.highlights !== undefined && (
                                <DarkroomSlider
                                  label="אזורים בהירים"
                                  track="highlights"
                                  value={correctionRecipe?.highlights ?? photographerFinalRecipe?.highlights ?? productionRecipe.highlights}
                                  aiValue={productionRecipe.highlights}
                                  min={-100}
                                  max={100}
                                  step={1}
                                  onChange={(value) => updateDarkroomValue("highlights", value)}
                                />
                              )}
                              {productionRecipe.shadows !== undefined && (
                                <DarkroomSlider
                                  label="צללים"
                                  track="shadows"
                                  value={correctionRecipe?.shadows ?? photographerFinalRecipe?.shadows ?? productionRecipe.shadows}
                                  aiValue={productionRecipe.shadows}
                                  min={-100}
                                  max={100}
                                  step={1}
                                  onChange={(value) => updateDarkroomValue("shadows", value)}
                                />
                              )}
                              {productionRecipe.whites !== undefined && (
                                <DarkroomSlider
                                  label="לבנים"
                                  track="whites"
                                  value={correctionRecipe?.whites ?? photographerFinalRecipe?.whites ?? productionRecipe.whites}
                                  aiValue={productionRecipe.whites}
                                  min={-100}
                                  max={100}
                                  step={1}
                                  onChange={(value) => updateDarkroomValue("whites", value)}
                                />
                              )}
                              {productionRecipe.blacks !== undefined && (
                                <DarkroomSlider
                                  label="שחורים"
                                  track="blacks"
                                  value={correctionRecipe?.blacks ?? photographerFinalRecipe?.blacks ?? productionRecipe.blacks}
                                  aiValue={productionRecipe.blacks}
                                  min={productionDarkroom.process_family === "legacy" ? 0 : -100}
                                  max={100}
                                  step={1}
                                  neutralValue={productionDarkroom.process_family === "legacy" ? 5 : 0}
                                  onChange={(value) => updateDarkroomValue("blacks", value)}
                                />
                              )}
                            </div>

                            {(productionRecipe.vibrance !== undefined ||
                              productionRecipe.saturation !== undefined ||
                              productionRecipe.clarity !== undefined) && (
                              <div className="darkroomControlSection">
                                <div className="darkroomSectionTitle">נוכחות וצבע</div>
                                {productionRecipe.clarity !== undefined && (
                                  <DarkroomSlider
                                    label="בהירות מקומית"
                                    track="clarity"
                                    value={correctionRecipe?.clarity ?? photographerFinalRecipe?.clarity ?? productionRecipe.clarity}
                                    aiValue={productionRecipe.clarity}
                                    min={-100}
                                    max={100}
                                    step={1}
                                    onChange={(value) => updateDarkroomValue("clarity", value)}
                                  />
                                )}
                                {productionRecipe.vibrance !== undefined && (
                                  <DarkroomSlider
                                    label="חיוניות"
                                    track="vibrance"
                                    value={correctionRecipe?.vibrance ?? photographerFinalRecipe?.vibrance ?? productionRecipe.vibrance}
                                    aiValue={productionRecipe.vibrance}
                                    min={-100}
                                    max={100}
                                    step={1}
                                    onChange={(value) => updateDarkroomValue("vibrance", value)}
                                  />
                                )}
                                {productionRecipe.saturation !== undefined && (
                                  <DarkroomSlider
                                    label="רוויה"
                                    value={correctionRecipe?.saturation ?? photographerFinalRecipe?.saturation ?? productionRecipe.saturation}
                                    aiValue={productionRecipe.saturation}
                                    min={-100}
                                    max={100}
                                    step={1}
                                    onChange={(value) => updateDarkroomValue("saturation", value)}
                                  />
                                )}
                              </div>
                            )}

                            {productionDarkroom.process_family === "legacy" &&
                              (productionRecipe.brightness !== undefined ||
                                productionRecipe.recovery !== undefined ||
                                productionRecipe.fill_light !== undefined) && (
                                <div className="darkroomControlSection legacyControlsSection">
                                  <div className="darkroomSectionTitle">Lightroom Legacy</div>
                                  {productionRecipe.brightness !== undefined && (
                                    <DarkroomSlider
                                      label="Brightness"
                                      value={correctionRecipe?.brightness ?? photographerFinalRecipe?.brightness ?? productionRecipe.brightness}
                                      aiValue={productionRecipe.brightness}
                                      min={-150}
                                      max={150}
                                      step={1}
                                      neutralValue={50}
                                      onChange={(value) => updateDarkroomValue("brightness", value)}
                                    />
                                  )}
                                  {productionRecipe.recovery !== undefined && (
                                    <DarkroomSlider
                                      label="Recovery"
                                      value={correctionRecipe?.recovery ?? photographerFinalRecipe?.recovery ?? productionRecipe.recovery}
                                      aiValue={productionRecipe.recovery}
                                      min={0}
                                      max={100}
                                      step={1}
                                      neutralValue={0}
                                      onChange={(value) => updateDarkroomValue("recovery", value)}
                                    />
                                  )}
                                  {productionRecipe.fill_light !== undefined && (
                                    <DarkroomSlider
                                      label="Fill Light"
                                      value={correctionRecipe?.fill_light ?? photographerFinalRecipe?.fill_light ?? productionRecipe.fill_light}
                                      aiValue={productionRecipe.fill_light}
                                      min={0}
                                      max={100}
                                      step={1}
                                      neutralValue={0}
                                      onChange={(value) => updateDarkroomValue("fill_light", value)}
                                    />
                                  )}
                                </div>
                              )}
                          </div>

                          <div className="darkroomControlFooter">
                            <div className="darkroomResetRow truthModeActions">
                              <div>
                                <button className="ghost" onClick={resetDarkroomToSource}>
                                  איפוס למקור
                                </button>
                                <button className="ghost" onClick={resetDarkroomToAi}>
                                  חזור להצעת ProGrapher
                                </button>
                                <button className="ghost" onClick={downloadAiXmpTest} disabled={xmpTestDownloading}>
                                  {xmpTestDownloading ? "מכין XMP..." : "הורד XMP לבדיקה ב-Lightroom"}
                                </button>
                              </div>
                              <span>
                                {darkroomSourceMode
                                  ? "מקור ללא שינוי"
                                  : correctionMode
                                  ? "Preview של תיקון ידני"
                                  : learningDecision
                                  ? "העריכה הסופית של הצלם"
                                  : "הצעת ה-AI הפעילה"}
                              </span>
                            </div>
                            <div className="productionLearningPanel">
                              {learningDecision ? (
                                <div className="productionLearningSaved">
                                  <div>
                                    <span>נשמר ללמידה</span>
                                    <strong>
                                      {learningDecision.verdict === "approved"
                                        ? "אושר ללא שינוי"
                                        : `נשמר תיקון · ${learningDecision.changed_parameter_count} פרמטרים`}
                                    </strong>
                                    <small>
                                      Profile V{learningDecision.profile_version_number} · {learningDecision.recipe_contract_version}
                                    </small>
                                  </div>
                                  <i aria-hidden="true">✓</i>
                                </div>
                              ) : (
                                <div className="productionLearningIntro">
                                  <strong>האם ProGrapher ערך נכון?</strong>
                                  <span>
                                    כל אישור או תיקון נשמר מול גרסת ה-Profile שיצרה את העריכה.
                                  </span>
                                </div>
                              )}

                              {feedbackSavedText && (
                                <div className="productionLearningMessage">{feedbackSavedText}</div>
                              )}

                              <div className="productionLearningActions">
                                {correctionMode ? (
                                  <>
                                    <button
                                      className="primary productionApproveButton"
                                      onClick={commitCorrection}
                                      disabled={feedbackLoading || correctionRendering}
                                    >
                                      {feedbackLoading ? "שומר..." : "שמור תיקון ולמד ממנו"}
                                    </button>
                                    <button
                                      className="ghost"
                                      onClick={cancelCorrectionMode}
                                      disabled={feedbackLoading}
                                    >
                                      ביטול
                                    </button>
                                  </>
                                ) : learningDecision ? (
                                  <>
                                    <button
                                      className="ghost"
                                      onClick={startCorrectionMode}
                                      disabled={feedbackLoading}
                                    >
                                      שנה את העריכה
                                    </button>
                                    {learningDecision.verdict === "corrected" && (
                                      <button
                                        className="ghost"
                                        onClick={resetDarkroomToAi}
                                        disabled={feedbackLoading}
                                      >
                                        חזור להצעת ProGrapher
                                      </button>
                                    )}
                                  </>
                                ) : (
                                  <>
                                    <button
                                      className="primary productionApproveButton"
                                      onClick={approveProductionEdit}
                                      disabled={feedbackLoading || darkroomSourceMode}
                                    >
                                      {feedbackLoading ? "שומר..." : darkroomSourceMode ? "חזור להצעת AI כדי לאשר" : "אשר את עריכת ProGrapher"}
                                    </button>
                                    <button
                                      className="ghost"
                                      onClick={startCorrectionMode}
                                      disabled={feedbackLoading}
                                    >
                                      אני רוצה לתקן
                                    </button>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                        </>
                      )}
                    </aside>
                  </div>
                </section>
              ) : (
                <div className="panel emptyState">לא נבחרה תמונה.</div>
              )}
            </>
          )}

          {view === "new-event" && (
            <section className="panel formPanel">
              <SectionHeader title="יצירת אירוע חדש" subtitle="האירוע והתמונות יישמרו ישירות במחשב המקומי, לא ב־Hostinger." />

              <div className="formGrid">
                <label>
                  שם האירוע
                  <input value={eventName} onChange={(e) => setEventName(e.target.value)} placeholder="לדוגמה: חתונת דניאל ונועה" />
                </label>
                <label>
                  תאריך האירוע
                  <input type="date" value={eventDate} onChange={(e) => setEventDate(e.target.value)} />
                </label>
              </div>

              <label>
                סוג האירוע
                <div className="typeGrid eventTypeGrid">
                  {["חתונה", "בר מצווה", "בת מצווה", "חינה", "אחר"].map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setEventType(type)}
                      className={eventType === type ? "selectedType" : ""}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              </label>

              {eventType === "אחר" && (
                <label className="customEventTypeField">
                  איזה אירוע?
                  <input
                    value={customEventType}
                    onChange={(e) => setCustomEventType(e.target.value)}
                    placeholder="לדוגמה: מסיבת אירוסין, יום הולדת..."
                  />
                </label>
              )}

              <label>
                הערה על סגנון האירוע
                <textarea value={styleNote} onChange={(e) => setStyleNote(e.target.value)} placeholder="לדוגמה: אולם כהה, תאורה חמה בחופה..." />
              </label>

              <div className="uploadBox realUpload" onDragOver={(e) => e.preventDefault()} onDrop={handleDrop} onClick={() => fileInputRef.current?.click()}>
                <input ref={fileInputRef} type="file" multiple accept=".cr2,.cr3,.nef,.arw,.dng,.orf,.rw2,.raf,.pef" onChange={handleFileInput} hidden />
                <strong>{files.length ? `${files.length} קבצים נבחרו` : "גרור לכאן את תמונות האירוע"}</strong>
                <span>RAW בלבד — CR2, CR3, NEF, ARW, DNG, ORF, RW2, RAF, PEF.</span>
                <button type="button" className="ghost" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}>בחירת קבצים</button>
              </div>

              {files.length > 0 && (
                <div className="selectedFiles">
                  <div className="selectedFilesHead">
                    <strong>קבצים שנבחרו</strong>
                    <button type="button" onClick={() => setFiles([])}>נקה הכל</button>
                  </div>
                  {files.slice(0, 8).map((file) => (
                    <div className="selectedFile" key={`${file.name}-${file.size}-${file.lastModified}`}>
                      <span>{file.name}</span>
                      <small>{formatBytes(file.size)}</small>
                    </div>
                  ))}
                </div>
              )}

              {uploadProgressText && <div className="progressMessage">{uploadProgressText}</div>}

              <div className="formActions">
                <button className="ghost" type="button" onClick={() => navigate("events")}>ביטול</button>
                <button className="primary" type="button" disabled={creatingEvent || !engineOnline} onClick={createRealEvent}>
                  {creatingEvent ? "מבצע..." : files.length ? "יצירת אירוע והעלאת תמונות" : "יצירת אירוע"}
                </button>
              </div>
            </section>
          )}

          {view === "style" && (
            <>
              <section className={`myStyleHero panel ${profileOverview?.profile_ready ? "ready" : "empty"}`}>
                <div className="myStyleHeroCopy">
                  <span>הסגנון שלי</span>
                  <h1>
                    {profileOverview?.profile_ready
                      ? "ProGrapher מכיר את דרך העריכה שלך"
                      : "בוא נלמד את דרך העריכה שלך"}
                  </h1>
                  <p>
                    {profileOverview?.profile_ready
                      ? "זה הפרופיל היחיד שבו ProGrapher משתמש כרגע באירועים חדשים. כל אישור ותיקון ממשיכים לחדד אותו."
                      : "חבר את Lightroom Classic פעם אחת. ProGrapher ילמד מהעריכות שכבר עשית ויבנה עבורך פרופיל AI אישי."}
                  </p>

                  <div className="myStyleHeroActions">
                    {profileOverview?.profile_ready ? (
                      <>
                        <button className="primary" onClick={() => navigate("new-event")}>
                          ערוך אירוע חדש
                        </button>
                        <button type="button" className="ghost" onClick={() => { resetStyleSetup(); navigate("style-setup"); }}>
                          ייבא חומר נוסף מ-Lightroom
                        </button>
                      </>
                    ) : (
                      <button type="button" className="primary" onClick={beginInitialStyleSetup}>
                        בנה את פרופיל ה-AI שלי
                      </button>
                    )}
                  </div>
                </div>

                <div className="myStyleActiveBadge">
                  <span>{profileOverview?.profile_ready ? "AI PROFILE ACTIVE" : "AI PROFILE"}</span>
                  <strong>
                    {profileOverview?.active_profile
                      ? `V${profileOverview.active_profile.version_number}`
                      : "—"}
                  </strong>
                  <small>
                    {profileOverview?.profile_ready
                      ? "פעיל באירועים חדשים"
                      : "עדיין לא נבנה"}
                  </small>
                </div>
              </section>

              {profileOverviewLoading && !profileOverview ? (
                <section className="myStyleLoading panel">
                  <i />
                  <div>
                    <strong>טוען את פרופיל ה-AI שלך</strong>
                    <span>רק רגע...</span>
                  </div>
                </section>
              ) : profileOverview?.profile_ready ? (
                <>
                  <section className="myStyleNumbers">
                    <div className="myStyleNumberCard">
                      <span>החלטות שנלמדו</span>
                      <strong>{profileOverview.learning.sample_count.toLocaleString()}</strong>
                      <small>אישורים ותיקונים מה-Darkroom</small>
                    </div>
                    <div className="myStyleNumberCard">
                      <span>אושרו ללא שינוי</span>
                      <strong>{profileOverview.learning.approved_count.toLocaleString()}</strong>
                      <small>הצעות שהיו נכונות כמו שהן</small>
                    </div>
                    <div className="myStyleNumberCard">
                      <span>תוקנו ידנית</span>
                      <strong>{profileOverview.learning.corrected_count.toLocaleString()}</strong>
                      <small>מהם ProGrapher לומד את ההבדלים</small>
                    </div>
                    <div className="myStyleNumberCard emphasis">
                      <span>קבלה ללא תיקון</span>
                      <strong>
                        {profileOverview.learning.acceptance_rate != null
                          ? `${profileOverview.learning.acceptance_rate}%`
                          : "—"}
                      </strong>
                      <small>
                        {profileOverview.learning.sample_count
                          ? "מתוך ההחלטות שנשמרו"
                          : "יופיע לאחר החלטות ראשונות"}
                      </small>
                    </div>
                  </section>

                  <section className="myStyleGrid">
                    <div className="myStyleIdentity panel">
                      <div className="myStyleSectionHead">
                        <div>
                          <span>הפרופיל האישי שלי</span>
                          <h2>{profileOverview.active_profile?.name || "הפרופיל המקצועי שלי"}</h2>
                        </div>
                        <i>✓</i>
                      </div>

                      <div className="myStyleInfoRows">
                        <div>
                          <span>גרסה פעילה</span>
                          <strong>V{profileOverview.active_profile?.version_number}</strong>
                        </div>
                        <div>
                          <span>מקור הסגנון</span>
                          <strong>{profileOverview.source?.label || "החלטות הצלם"}</strong>
                        </div>
                        <div>
                          <span>קטלוג</span>
                          <strong>{profileOverview.source?.catalog_name || "—"}</strong>
                        </div>
                        <div>
                          <span>עודכן לאחרונה</span>
                          <strong>
                            {profileOverview.active_profile?.activated_at
                              ? new Date(profileOverview.active_profile.activated_at).toLocaleDateString("he-IL")
                              : "—"}
                          </strong>
                        </div>
                      </div>

                      <div className="myStyleTagsBlock">
                        <span>איך הגדרת את הסגנון שלך</span>
                        <div>
                          {(profileOverview.photographer_preferences.style_words || []).length ? (
                            profileOverview.photographer_preferences.style_words.map((item) => (
                              <b key={item}>{item}</b>
                            ))
                          ) : (
                            <small>אפשר לעדכן את תיאור הסגנון בפרופיל שלך.</small>
                          )}
                        </div>
                      </div>

                      <div className="myStylePriorities">
                        <span>מה חשוב לך במיוחד</span>
                        <div>
                          {(profileOverview.photographer_preferences.priorities || []).length ? (
                            profileOverview.photographer_preferences.priorities.map((item) => (
                              <b key={item}>{item}</b>
                            ))
                          ) : (
                            <small>עדיין לא הוגדרו עדיפויות.</small>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="myStyleGrowth panel">
                      <div className="myStyleSectionHead">
                        <div>
                          <span>שיפור מתמשך</span>
                          <h2>הפרופיל שלך ממשיך ללמוד</h2>
                        </div>
                      </div>

                      {profileOverview.candidate?.status === "ready" ? (
                        <div className="myStyleCandidateReady">
                          <span>גרסה משופרת מוכנה</span>
                          <strong>V{profileOverview.candidate.version_number}</strong>
                          <p>
                            ProGrapher בדק את הגרסה החדשה על חומר Validation נפרד.
                            היא לא תחליף את הפרופיל הפעיל בלי אישור שלך.
                          </p>
                          <button
                            className="primary"
                            onClick={activateCandidateProfile}
                            disabled={retrainingLoading}
                          >
                            {retrainingLoading
                              ? "מפעיל..."
                              : `הפעל V${profileOverview.candidate.version_number}`}
                          </button>
                        </div>
                      ) : profileOverview.growth?.latest_run_status &&
                        ["queued", "running"].includes(profileOverview.growth.latest_run_status) ? (
                        <div className="myStyleGrowthRunning">
                          <div>
                            <strong>בודק גרסה משופרת</strong>
                            <span>ProGrapher מאמת שהשינוי באמת משפר את העריכה שלך.</span>
                          </div>
                          <b>{profileOverview.growth.latest_run_progress}%</b>
                        </div>
                      ) : (
                        <>
                          <div className="myStyleGrowthProgress">
                            <div>
                              <span>התקדמות לגרסה הבאה</span>
                              <strong>
                                {profileOverview.growth?.ready_for_candidate
                                  ? "מוכן לבדיקה"
                                  : profileOverview.growth?.remaining_samples
                                    ? `עוד ${profileOverview.growth.remaining_samples} החלטות`
                                    : "ממשיך ללמוד"}
                              </strong>
                            </div>
                            <i>
                              <b
                                style={{
                                  width: `${Math.min(
                                    100,
                                    profileOverview.growth?.ready_for_candidate
                                      ? 100
                                      : ((profileOverview.learning.sample_count || 0) /
                                          Math.max(1, profileOverview.growth?.minimum_samples || 20)) *
                                        100
                                  )}%`,
                                }}
                              />
                            </i>
                          </div>

                          <div className="myStyleLearningExplanation">
                            <div><i>1</i><span><strong>ProGrapher עורך</strong><small>לפי הפרופיל הפעיל.</small></span></div>
                            <div><i>2</i><span><strong>אתה מאשר או מתקן</strong><small>כל החלטה נשמרת.</small></span></div>
                            <div><i>3</i><span><strong>הפרופיל משתפר</strong><small>רק אם Validation מוכיח שיפור.</small></span></div>
                          </div>

                          <button
                            className="primary myStyleImproveButton"
                            onClick={startAdaptiveRetraining}
                            disabled={
                              retrainingLoading ||
                              !profileOverview.growth?.ready_for_candidate
                            }
                          >
                            {retrainingLoading
                              ? "מכין גרסה..."
                              : profileOverview.growth?.ready_for_candidate
                                ? "בדוק גרסה משופרת"
                                : "ProGrapher עדיין אוסף החלטות"}
                          </button>
                        </>
                      )}
                    </div>
                  </section>

                  <section className="myStylePromise panel">
                    <div>
                      <span>מה ProGrapher עושה בשבילך</span>
                      <h3>לא צריך להבין מודלים, מדדים או Dataset.</h3>
                      <p>
                        אתה עורך כמו תמיד. ProGrapher זוכר מה אישרת, מה תיקנת ואיזה Profile עשה את ההחלטה —
                        ומשפר את עצמו מאחורי הקלעים.
                      </p>
                    </div>
                    <div className="myStylePromiseChecks">
                      <span>✓ הפרופיל הפעיל נשמר בגרסאות</span>
                      <span>✓ Candidate חדש לא מופעל אוטומטית</span>
                      <span>✓ התיקונים שלך נשארים גם אם אירוע נמחק</span>
                    </div>
                  </section>
                </>
              ) : (
                <section className="myStyleEmptyState panel">
                  <div className="myStyleEmptyIcon">AI</div>
                  <div>
                    <h2>עדיין אין פרופיל AI פעיל</h2>
                    <p>
                      נתחיל מהעריכות שכבר עשית ב-Lightroom Classic. החיבור הוא Read Only והקטלוג המקורי לא משתנה.
                    </p>
                    <button type="button" className="primary" onClick={beginInitialStyleSetup}>
                      חבר את Lightroom ובנה פרופיל
                    </button>
                  </div>
                </section>
              )}
            </>
          )}

          {view === "style-setup" && (
            <>
              <section className="styleSetupHero panel">
                <button className="styleSetupBack" onClick={() => navigate("style")}>← חזרה לסגנון שלי</button>
                <span>AI PROFILE SETUP</span>
                <h1>{profileOverview?.profile_ready ? "ייבוא חומר Lightroom נוסף" : "בניית פרופיל ה-AI שלך"}</h1>
                <p>
                  ProGrapher מטפל בכל שלבי הבדיקה והאימון מאחורי הקלעים. כאן תראה רק מה צריך לעשות עכשיו.
                </p>
              </section>

              <section className="styleSetupPanel panel">
                {!lightroomAnalysis && !lightroomDatasetBuild ? (
                  <div className="styleSetupStart">
                    <div className="styleSetupStepMark">1</div>
                    <div>
                      <h2>מצא את קטלוג Lightroom Classic</h2>
                      <p>נאתר את הקטלוג במחשב ונלמד רק מהעריכות שכבר קיימות בו.</p>
                    </div>
                    <button
                      className="primary"
                      onClick={scanLightroomCatalogs}
                      disabled={lightroomScanLoading || lightroomAnalyzeLoading}
                    >
                      {lightroomScanLoading || lightroomAnalyzeLoading
                        ? "מחפש ומנתח..."
                        : "מצא את Lightroom שלי"}
                    </button>

                    {lightroomCatalogs.length > 1 && (
                      <div className="styleSetupCatalogs">
                        {lightroomCatalogs.map((catalog) => (
                          <button key={catalog.path} onClick={() => analyzeLightroomCatalog(catalog.path)}>
                            <strong>{catalog.name}</strong>
                            <span>{catalog.source} · {catalog.size_mb} MB</span>
                          </button>
                        ))}
                      </div>
                    )}

                    <details className="styleSetupManual">
                      <summary>הקטלוג נמצא במקום אחר</summary>
                      <div>
                        <input
                          value={lightroomManualPath}
                          onChange={(e) => setLightroomManualPath(e.target.value)}
                          placeholder={'C:\\Users\\...\\Catalog.lrcat'}
                        />
                        <button
                          className="ghost"
                          onClick={() => analyzeLightroomCatalog()}
                          disabled={!lightroomManualPath.trim()}
                        >
                          פתח קטלוג
                        </button>
                      </div>
                    </details>
                  </div>
                ) : lightroomAnalysis && !lightroomDatasetBuild ? (
                  <div className="styleSetupSelection">
                    <div className="styleSetupStepMark">2</div>
                    <div className="styleSetupSelectionHead">
                      <div>
                        <h2>בחר מאיזה סגנון ללמוד</h2>
                        <p>{lightroomAnalysis.readiness.message_he}</p>
                      </div>
                      <button className="ghost" onClick={resetStyleSetup}>החלף קטלוג</button>
                    </div>

                    <div className="styleSetupSourceSummary">
                      <div><span>קטלוג</span><strong>{lightroomAnalysis.catalog.name}</strong></div>
                      <div><span>תמונות מקור</span><strong>{lightroomAnalysis.summary.source_photo_count.toLocaleString()}</strong></div>
                      <div><span>חומר מתאים</span><strong>{lightroomAnalysis.summary.edited_source_photo_count.toLocaleString()}</strong></div>
                    </div>

                    {lightroomAnalysis.training_groups.length > 0 && (
                      <div className="styleSetupGroups">
                        {lightroomAnalysis.training_groups.map((group) => {
                          const selected = lightroomSelectedCollections.includes(group.id);
                          return (
                            <button
                              key={group.id}
                              className={selected ? "selected" : ""}
                              onClick={() => toggleLightroomCollection(group.id)}
                            >
                              <i>{selected ? "✓" : ""}</i>
                              <div>
                                <strong>{group.display_name || group.name}</strong>
                                <span>{group.photo_count.toLocaleString()} תמונות ערוכות</span>
                              </div>
                              {group.recommended && <em>מומלץ</em>}
                            </button>
                          );
                        })}
                      </div>
                    )}

                    <label className="styleSetupName">
                      שם הפרופיל
                      <input
                        value={lightroomProfileName}
                        onChange={(e) => setLightroomProfileName(e.target.value)}
                      />
                    </label>

                    <button
                      className="primary styleSetupContinue"
                      onClick={saveLightroomProfileDraft}
                      disabled={
                        lightroomDraftSaving ||
                        (lightroomAnalysis.training_groups.length > 0 &&
                          lightroomSelectedCollections.length === 0)
                      }
                    >
                      {lightroomDraftSaving ? "מכין..." : "התחל לבנות את הפרופיל"}
                    </button>
                  </div>
                ) : (
                  <div className="styleSetupBuild">
                    <div className="styleSetupStepMark">3</div>
                    <div className="styleSetupBuildHead">
                      <div>
                        <h2>ProGrapher בונה את הפרופיל שלך</h2>
                        <p>אפשר להשאיר את המסך פתוח. שלבים שכבר הושלמו לא יחושבו מחדש.</p>
                      </div>
                      <button className="ghost" onClick={resetStyleSetup}>התחל מחדש</button>
                    </div>

                    <div className="styleSetupTimeline">
                      <StyleSetupStage
                        label="חיבור תמונות לעריכות"
                        done={lightroomDatasetBuild?.status === "completed"}
                        active={lightroomDatasetBuild?.status === "building"}
                        detail={
                          lightroomDatasetBuild?.status === "building"
                            ? `${lightroomDatasetBuild.progress_percent}%`
                            : lightroomDatasetBuild?.status === "completed"
                              ? `${(lightroomDatasetBuild.manifest.valid_pairs || 0).toLocaleString()} התאמות`
                              : "ממתין"
                        }
                      />
                      <StyleSetupStage
                        label="בדיקת חומר הלמידה"
                        done={lightroomDatasetAudit?.status === "completed" && !!lightroomDatasetAudit.result?.passed}
                        active={!!lightroomDatasetAudit && ["queued", "building"].includes(lightroomDatasetAudit.status)}
                        detail={
                          lightroomDatasetAudit?.status === "completed" && lightroomDatasetAudit.result?.passed
                            ? "תקין"
                            : lightroomDatasetAudit
                              ? `${lightroomDatasetAudit.progress_percent}%`
                              : "ממתין"
                        }
                      />
                      <StyleSetupStage
                        label="היכרות חזותית עם התמונות"
                        done={lightroomVisionJob?.status === "completed"}
                        active={!!lightroomVisionJob && !["completed", "failed"].includes(lightroomVisionJob.status)}
                        detail={
                          lightroomVisionJob?.status === "completed"
                            ? "מוכן"
                            : lightroomVisionJob
                              ? `${lightroomVisionJob.progress_percent}%`
                              : "ממתין"
                        }
                      />
                      <StyleSetupStage
                        label="לימוד דרך העריכה"
                        done={lightroomTrainingRun?.status === "completed"}
                        active={!!lightroomTrainingRun && !["completed", "failed"].includes(lightroomTrainingRun.status)}
                        detail={
                          lightroomTrainingRun?.status === "completed"
                            ? "מוכן"
                            : lightroomTrainingRun
                              ? `${lightroomTrainingRun.progress_percent}%`
                              : "ממתין"
                        }
                      />
                      <StyleSetupStage
                        label="הכנת פרופיל Production"
                        done={trainingV2Run?.status === "completed"}
                        active={!!trainingV2Run && !["completed", "failed"].includes(trainingV2Run.status)}
                        detail={
                          trainingV2Run?.status === "completed"
                            ? "מוכן להפעלה"
                            : trainingV2Run
                              ? `${trainingV2Run.progress_percent}%`
                              : "ממתין"
                        }
                      />
                    </div>

                    {lightroomDatasetBuild?.status === "failed" ||
                    lightroomDatasetAudit?.status === "failed" ||
                    lightroomVisionJob?.status === "failed" ||
                    lightroomTrainingRun?.status === "failed" ||
                    trainingV2Run?.status === "failed" ? (
                      <div className="styleSetupProblem">
                        <strong>הבנייה נעצרה</strong>
                        <p>
                          אפשר לפתוח את Diagnostics כדי לראות את הסיבה המלאה, או להתחיל מחדש.
                        </p>
                        <button className="ghost" onClick={() => navigate("diagnostics")}>
                          פתח אבחון מתקדם
                        </button>
                      </div>
                    ) : null}

                    {lightroomVisionJob?.status === "completed" && !lightroomTrainingRun && (
                      <button
                        className="primary styleSetupNextAction"
                        onClick={startLightroomTraining}
                        disabled={lightroomTrainingStarting}
                      >
                        {lightroomTrainingStarting ? "מתחיל..." : "המשך לבניית פרופיל העריכה"}
                      </button>
                    )}

                    {lightroomTrainingRun?.status === "completed" &&
                      !trainingV2Run && (
                        <button
                          className="primary styleSetupNextAction"
                          onClick={startTrainingV2}
                          disabled={trainingV2Starting}
                        >
                          {trainingV2Starting ? "מסיים..." : "סיים את בניית פרופיל ה-AI"}
                        </button>
                      )}

                    {trainingV2Run?.status === "completed" && (
                      <div className="styleSetupReady">
                        <i>✓</i>
                        <div>
                          <strong>הפרופיל מוכן להפעלה</strong>
                          <span>מכאן ProGrapher יכול להתחיל לערוך אירועים חדשים.</span>
                        </div>
                        <button
                          className="primary"
                          onClick={finalizeInitialAiProfile}
                          disabled={lightroomTrainingStarting}
                        >
                          {lightroomTrainingStarting ? "מפעיל..." : "הפעל את הפרופיל שלי"}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                <div className="styleSetupPrivacy">
                  <span>🔒</span>
                  <div>
                    <strong>הקטלוג נקרא ב-Read Only</strong>
                    <small>ProGrapher לא משנה את קטלוג Lightroom ולא נוגע בקבצי המקור.</small>
                  </div>
                </div>
              </section>
            </>
          )}

          {view === "diagnostics" && (
            <>
              <section className="diagnosticsHero panel">
                <div>
                  <span>DEVELOPER DIAGNOSTICS</span>
                  <h2>אבחון AI מתקדם</h2>
                  <p>
                    Dataset, Vision, Training, Evaluation, Recipe Intelligence ונתוני מחקר.
                    המסך הזה מיועד לפיתוח ואבחון בלבד ואינו חלק מחוויית הצלם.
                  </p>
                </div>
                <button className="ghost" onClick={() => navigate("system")}>חזרה לכלי מערכת</button>
              </section>
              <section className="profileEvolutionCard panel">
                <div className="profileEvolutionHead">
                  <div>
                    <span>MY AI PROFILE</span>
                    <h2>הסגנון שלך משתפר מכל החלטה</h2>
                    <p>
                      ProGrapher שומר אישורים ותיקונים מה-Darkroom, בודק אותם על Validation נפרד
                      ויוצר גרסה חדשה רק אם היא באמת משתפרת.
                    </p>
                  </div>
                  <div className="profileEvolutionVersion">
                    <span>ACTIVE</span>
                    <strong>
                      V{retrainingStatus?.active_profile?.version_number ?? "—"}
                    </strong>
                  </div>
                </div>

                {!retrainingStatus?.active_profile ? (
                  <div className="profileEvolutionEmpty">
                    <strong>עדיין אין AI Profile פעיל</strong>
                    <span>לאחר סיום בניית הסגנון, מנגנון השיפור האוטומטי יופיע כאן.</span>
                  </div>
                ) : (
                  <>
                    <div className="profileEvolutionStats">
                      <div>
                        <span>החלטות שנלמדו</span>
                        <strong>{retrainingStatus.readiness.sample_count}</strong>
                        <small>
                          {retrainingStatus.readiness.remaining_samples > 0
                            ? `עוד ${retrainingStatus.readiness.remaining_samples} החלטות חדשות עד גרסה חדשה`
                            : "מספיק ליצירת Candidate"}
                        </small>
                      </div>
                      <div>
                        <span>אושרו ללא שינוי</span>
                        <strong>{retrainingStatus.readiness.approved_count}</strong>
                        <small>אות חזק שה-AI כבר בכיוון הנכון</small>
                      </div>
                      <div>
                        <span>תוקנו ע"י הצלם</span>
                        <strong>{retrainingStatus.readiness.corrected_count}</strong>
                        <small>מהם ProGrapher לומד את ההבדלים</small>
                      </div>
                    </div>

                    <div className="profileEvolutionProgress">
                      <div>
                        <span>
                          {Math.min(
                            100,
                            Math.round(
                              (retrainingStatus.readiness.sample_count /
                                Math.max(1, retrainingStatus.readiness.minimum_samples)) *
                                100
                            )
                          )}%
                        </span>
                        <strong>
                          {retrainingStatus.readiness.ready
                            ? "מוכן לבדוק גרסה משופרת"
                            : `אוספים ${retrainingStatus.readiness.minimum_samples} החלטות ראשונות`}
                        </strong>
                      </div>
                      <i>
                        <b
                          style={{
                            width: `${Math.min(
                              100,
                              (retrainingStatus.readiness.sample_count /
                                Math.max(1, retrainingStatus.readiness.minimum_samples)) *
                                100
                            )}%`,
                          }}
                        />
                      </i>
                    </div>

                    {retrainingStatus.latest_run &&
                      ["queued", "running"].includes(retrainingStatus.latest_run.status) && (
                        <div className="profileEvolutionTraining">
                          <div>
                            <span>BUILDING CANDIDATE</span>
                            <strong>ProGrapher בודק אם הוא יכול להשתפר</strong>
                            <small>
                              TRAIN {retrainingStatus.latest_run.train_count || "—"} · VALIDATION{" "}
                              {retrainingStatus.latest_run.validation_count || "—"}
                            </small>
                          </div>
                          <b>{retrainingStatus.latest_run.progress_percent}%</b>
                        </div>
                      )}

                    {retrainingStatus.latest_run?.status === "no_improvement" && (
                      <div className="profileEvolutionNoChange">
                        <strong>הפרופיל הפעיל עדיין טוב יותר</strong>
                        <span>
                          בדקנו את התיקונים החדשים על Validation ולא החלפנו את המודל כי לא נמצא שיפור אמיתי.
                        </span>
                      </div>
                    )}

                    {retrainingStatus.candidate_version &&
                      retrainingStatus.candidate_version.status === "ready" && (
                        <div className="profileCandidateReady">
                          <div>
                            <span>NEW PROFILE READY</span>
                            <strong>
                              Candidate V{retrainingStatus.candidate_version.version_number} מוכן
                            </strong>
                            <small>
                              {(retrainingStatus.candidate_version.summary?.adapted_target_count || 0)} פרמטרים השתפרו
                              {typeof retrainingStatus.candidate_version.summary?.mean_selected_validation_improvement_percent === "number"
                                ? ` · שיפור Validation ממוצע ${retrainingStatus.candidate_version.summary.mean_selected_validation_improvement_percent}%`
                                : ""}
                            </small>
                          </div>
                          <button
                            className="primary"
                            onClick={activateCandidateProfile}
                            disabled={retrainingLoading}
                          >
                            {retrainingLoading
                              ? "מפעיל..."
                              : `הפעל V${retrainingStatus.candidate_version.version_number}`}
                          </button>
                        </div>
                      )}

                    {!retrainingStatus.candidate_version ||
                    retrainingStatus.candidate_version.status !== "ready" ? (
                      <div className="profileEvolutionActions">
                        <button
                          className="primary"
                          onClick={startAdaptiveRetraining}
                          disabled={
                            retrainingLoading ||
                            !retrainingStatus.readiness.ready ||
                            !!(
                              retrainingStatus.latest_run &&
                              ["queued", "running"].includes(retrainingStatus.latest_run.status)
                            )
                          }
                        >
                          {retrainingLoading
                            ? "מתחיל..."
                            : retrainingStatus.readiness.ready
                              ? "צור גרסה משופרת"
                              : `עוד ${retrainingStatus.readiness.remaining_samples} החלטות נדרשות`}
                        </button>
                        <span>
                          Candidate חדש לעולם לא מחליף את ה-Active Profile בלי אישור מפורש.
                        </span>
                      </div>
                    ) : null}
                  </>
                )}
              </section>

              <section className="lightroomImporter lightroomImporterSimple panel">
                <div className="lightroomSimpleHero">
                  <div>
                    <span className="lightroomImporterEyebrow">PROFESSIONAL AI PROFILE</span>
                    <h2>חבר את Lightroom. אנחנו נעשה את השאר.</h2>
                    <p>
                      ProGrapher ימצא את הקטלוג, יזהה את תמונות המקור והעריכות שלך,
                      ימפה את חומר הלמידה ויכין פרופיל AI אישי — בלי שתצטרך להבין איך Lightroom שומר את המידע.
                    </p>
                  </div>
                  <div className="lightroomSourceBadge">
                    <strong>LrC</strong>
                    <span>Lightroom Classic</span>
                  </div>
                </div>

                {!lightroomAnalysis && (
                  <div className="lightroomConnectArea">
                    <button
                      className="lightroomConnectButton"
                      onClick={scanLightroomCatalogs}
                      disabled={lightroomScanLoading || lightroomAnalyzeLoading || !engineOnline}
                    >
                      <span className="lightroomConnectIcon">LrC</span>
                      <span>
                        <strong>
                          {lightroomScanLoading
                            ? "מחפש את Lightroom במחשב..."
                            : lightroomAnalyzeLoading
                              ? "לומד את הקטלוג..."
                              : "חבר את Lightroom"}
                        </strong>
                        <small>חיפוש וניתוח אוטומטיים דרך ProGrapher Local Engine</small>
                      </span>
                    </button>

                    {(lightroomScanLoading || lightroomAnalyzeLoading) && (
                      <div className="lightroomAutoProgress">
                        <div className="lightroomProgressPulse" />
                        <div>
                          <strong>ProGrapher מנתח את סביבת העריכה שלך</strong>
                          <span>קטלוג ← תמונות מקור ← עריכות ← קבוצות צילום ← חומר ללמידה</span>
                        </div>
                      </div>
                    )}

                    {lightroomCatalogs.length > 1 && !lightroomAnalyzeLoading && (
                      <div className="lightroomCatalogChoice">
                        <div className="lightroomChoiceTitle">
                          <strong>מצאנו {lightroomCatalogs.length} קטלוגים</strong>
                          <span>בחר את הקטלוג שמכיל את העריכות שמהן נלמד.</span>
                        </div>
                        <div className="lightroomCatalogGrid simple">
                          {lightroomCatalogs.map((catalog) => (
                            <button
                              className="lightroomCatalogCard"
                              key={catalog.path}
                              onClick={() => analyzeLightroomCatalog(catalog.path)}
                            >
                              <div className="lightroomCatalogIcon">LrC</div>
                              <div className="lightroomCatalogText">
                                <strong>{catalog.name}</strong>
                                <span>{catalog.source} · {catalog.size_mb} MB</span>
                                <small title={catalog.path}>{catalog.path}</small>
                              </div>
                              <i>←</i>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {!lightroomScanLoading && !lightroomAnalyzeLoading && (
                      <details className="lightroomManualFallback">
                        <summary>הקטלוג שלי נמצא במקום אחר</summary>
                        <div>
                          <input
                            value={lightroomManualPath}
                            onChange={(e) => setLightroomManualPath(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") analyzeLightroomCatalog();
                            }}
                            placeholder={'C:\\Users\\Matan\\Pictures\\Lightroom\\Catalog.lrcat'}
                          />
                          <button
                            className="ghost"
                            onClick={() => analyzeLightroomCatalog()}
                            disabled={!lightroomManualPath.trim()}
                          >
                            פתח קטלוג
                          </button>
                        </div>
                      </details>
                    )}
                  </div>
                )}

                {lightroomAnalysis && !lightroomDatasetBuild && (
                  <div className="lightroomFriendlyResult">
                    <div className="lightroomFriendlyHeader">
                      <div>
                        <span className={`lightroomReadiness ${lightroomAnalysis.readiness.state}`}>
                          <i /> {lightroomAnalysis.readiness.score >= 85 ? "מוכן ללמידה" : "הקטלוג נותח"}
                        </span>
                        <h3>מצאנו את סביבת העריכה שלך</h3>
                        <p>{lightroomAnalysis.readiness.message_he}</p>
                      </div>
                      <button
                        className="ghost subtle"
                        onClick={() => {
                          setLightroomAnalysis(null);
                          setLightroomSelectedCollections([]);
                          setLightroomDatasetBuild(null);
                          setLightroomActiveProfileId("");
                          if (typeof window !== "undefined") {
                            window.localStorage.removeItem("prographer_active_ai_profile_import");
                          }
                        }}
                      >
                        החלף קטלוג
                      </button>
                    </div>

                    <div className="lightroomFriendlyStats">
                      <div>
                        <span>תמונות מקור</span>
                        <strong>{lightroomAnalysis.summary.source_photo_count.toLocaleString()}</strong>
                        <small>{lightroomAnalysis.summary.raw_count.toLocaleString()} RAW</small>
                      </div>
                      <div>
                        <span>תמונות עם עריכה</span>
                        <strong>{lightroomAnalysis.summary.edited_source_photo_count.toLocaleString()}</strong>
                        <small>זוהו אוטומטית</small>
                      </div>
                      <div>
                        <span>חומר זמין במחשב</span>
                        <strong>{Math.round(lightroomAnalysis.summary.files_available_percent)}%</strong>
                        <small>{lightroomAnalysis.summary.files_available_count.toLocaleString()} קבצים נמצאו</small>
                      </div>
                      <div>
                        <span>
                          {lightroomAnalysis.style_discovery?.mode === "style_variants"
                            ? "סגנונות שנמצאו"
                            : "חומר מתאים ללמידה"}
                        </span>
                        <strong>
                          {(lightroomAnalysis.style_discovery?.candidate_count ??
                            lightroomAnalysis.summary.style_candidate_count ??
                            lightroomAnalysis.summary.training_group_count).toLocaleString()}
                        </strong>
                        <small>
                          {lightroomAnalysis.style_discovery?.mode === "style_variants"
                            ? "גרסאות טכניות סוננו אוטומטית"
                            : "נבחר אוטומטית מהקטלוג"}
                        </small>
                      </div>
                    </div>

                    <div className="lightroomFriendlyChecks">
                      <div><i>✓</i><span><strong>תמונות המקור זוהו</strong><small>ProGrapher הפריד קבצים אמיתיים מגרסאות Lightroom פנימיות.</small></span></div>
                      <div><i>✓</i><span><strong>העריכות זוהו</strong><small>החלטות העריכה ממופות מאחורי הקלעים באופן אוטומטי.</small></span></div>
                      <div><i>✓</i><span><strong>החומר סונן אוטומטית</strong><small>גרסאות Copy, Inputs וקבוצות מערכת נשארות מאחורי הקלעים ולא מבלבלות את הצלם.</small></span></div>
                    </div>

                    <div className="lightroomTrainingPicker">
                      <div className="lightroomPickerHead">
                        <div>
                          <span>
                            {lightroomAnalysis.style_discovery?.mode === "style_variants"
                              ? "איזה סגנון תרצה ללמד את ProGrapher?"
                              : "איזה חומר תרצה ללמד את ProGrapher?"}
                          </span>
                          <h4>
                            {lightroomAnalysis.style_discovery?.title_he ||
                              (lightroomAnalysis.training_groups.length
                                ? "בחר חומר ללמידה"
                                : "הקטלוג כולו מוכן ללמידה")}
                          </h4>
                          <p>
                            {lightroomAnalysis.style_discovery?.description_he ||
                              (lightroomAnalysis.training_groups.length
                                ? "בחר את הקבוצה שמתאימה לפרופיל שאתה יוצר עכשיו."
                                : "לא צריך לבחור שום דבר נוסף. נשתמש בכל חומר העריכה המתאים שמצאנו.")}
                          </p>
                        </div>
                        {lightroomSelectedCollections.length > 0 && (
                          <span className="lightroomSelectedCount">
                            {lightroomAnalysis.style_discovery?.selection_mode === "single"
                              ? "סגנון נבחר"
                              : `${lightroomSelectedCollections.length} נבחרו`}
                          </span>
                        )}
                      </div>

                      {lightroomAnalysis.training_groups.length > 0 && (
                        <div className="lightroomTrainingGroups">
                          {lightroomAnalysis.training_groups.map((group) => {
                            const selected = lightroomSelectedCollections.includes(group.id);
                            return (
                              <button
                                key={`${group.kind}-${group.id}`}
                                className={`${selected ? "selected" : ""} ${group.recommended ? "recommended" : ""}`}
                                onClick={() => toggleLightroomCollection(group.id)}
                              >
                                <span className="lightroomGroupCheck">{selected ? "✓" : ""}</span>
                                <span className="lightroomGroupCopy">
                                  <strong>{group.display_name || group.name}</strong>
                                  <small>
                                    {group.photo_count.toLocaleString()} תמונות ערוכות
                                    {typeof group.coverage_percent === "number" && group.coverage_percent >= 80
                                      ? " · כיסוי מלא"
                                      : ""}
                                  </small>
                                </span>
                                <em className={group.recommended ? "recommendedBadge" : "suitableBadge"}>
                                  {group.badge_he || (group.recommended ? "מומלץ" : "מתאים ללמידה")}
                                </em>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    <div className="lightroomProfileFooter friendly">
                      <label>
                        שם פרופיל ה־AI
                        <input
                          value={lightroomProfileName}
                          onChange={(e) => setLightroomProfileName(e.target.value)}
                        />
                      </label>
                      <div>
                        <span className="lightroomPrivacyNote">הקטלוג נקרא במצב Read Only דרך המחשב שלך.</span>
                        <button
                          className="lightroomCreateProfileButton"
                          onClick={saveLightroomProfileDraft}
                          disabled={
                            lightroomDraftSaving ||
                            (lightroomAnalysis.training_groups.length > 0 &&
                              lightroomSelectedCollections.length === 0) ||
                            (lightroomAnalysis.style_discovery?.selection_mode === "single" &&
                              lightroomSelectedCollections.length > 1)
                          }
                        >
                          {lightroomDraftSaving ? "מכין את הפרופיל..." : "צור את פרופיל ה־AI שלי"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </section>

              {lightroomDatasetBuild && (
                <section className="lightroomDatasetBuild panel">
                  <div className="datasetBuildHero">
                    <div>
                      <span className={`datasetBuildStatus ${lightroomDatasetBuild.status}`}>
                        <i /> {lightroomDatasetBuild.status === "completed" ? "Dataset מוכן" : lightroomDatasetBuild.status === "failed" ? "נדרשת בדיקה" : "בונה פרופיל AI"}
                      </span>
                      <h2>
                        {lightroomDatasetBuild.status === "completed"
                          ? "חומר הלמידה שלך מוכן"
                          : lightroomDatasetBuild.status === "failed"
                          ? "לא הצלחנו להשלים את חומר הלמידה"
                          : "מכינים את פרופיל ה־AI שלך"}
                      </h2>
                      <p>
                        {lightroomDatasetBuild.status === "completed"
                          ? "ProGrapher חיבר את תמונות המקור לעריכות Lightroom, אימת את ההתאמות ונעל סט בדיקה נפרד."
                          : lightroomDatasetBuild.status === "failed"
                          ? lightroomDatasetBuild.error || "אירעה שגיאה בזמן בניית ה-Dataset."
                          : lightroomDatasetBuild.stage_he}
                      </p>
                    </div>
                    <div className="datasetBuildPercent">
                      <strong>{Math.max(0, Math.min(100, lightroomDatasetBuild.progress_percent))}%</strong>
                      <span>התקדמות</span>
                    </div>
                  </div>

                  <div className="datasetProgressTrack">
                    <i style={{ width: `${Math.max(0, Math.min(100, lightroomDatasetBuild.progress_percent))}%` }} />
                  </div>

                  <div className="datasetBuildSteps">
                    {[
                      ["reading_lightroom", "קטלוג Lightroom נותח"],
                      ["mapping_pairs", "הסגנון שנבחר מחובר לתמונות המקור"],
                      ["matching_files", "קבצי המקור מאומתים במחשב"],
                      ["extracting_recipes", "החלטות העריכה של Lightroom נקראות"],
                      ["validating_pairs", "ההתאמות נבדקות אחת־לאחת"],
                      ["writing_dataset", "Train / Validation / Test נוצרים"],
                    ].map(([stage, label], index, arr) => {
                      const order = arr.map(([s]) => s);
                      const currentIndex = order.indexOf(lightroomDatasetBuild.stage);
                      const done = lightroomDatasetBuild.status === "completed" || (currentIndex >= 0 && index < currentIndex);
                      const active = lightroomDatasetBuild.status === "building" && stage === lightroomDatasetBuild.stage;
                      return (
                        <div className={`${done ? "done" : ""} ${active ? "active" : ""}`} key={stage}>
                          <i>{done ? "✓" : active ? "•" : ""}</i>
                          <span>{label}</span>
                        </div>
                      );
                    })}
                  </div>

                  {lightroomDatasetBuild.status === "completed" && (
                    <div className="datasetReadySummary">
                      <div>
                        <span>התאמות תקינות</span>
                        <strong>{(lightroomDatasetBuild.manifest.valid_pairs || 0).toLocaleString()}</strong>
                        <small>RAW ↔ עריכת Lightroom</small>
                      </div>
                      <div>
                        <span>אימון</span>
                        <strong>{(lightroomDatasetBuild.manifest.splits?.train || 0).toLocaleString()}</strong>
                        <small>TRAIN</small>
                      </div>
                      <div>
                        <span>בקרה</span>
                        <strong>{(lightroomDatasetBuild.manifest.splits?.validation || 0).toLocaleString()}</strong>
                        <small>VALIDATION</small>
                      </div>
                      <div>
                        <span>בדיקה סופית</span>
                        <strong>{(lightroomDatasetBuild.manifest.splits?.test || 0).toLocaleString()}</strong>
                        <small>TEST · נעול</small>
                      </div>
                    </div>
                  )}

                  {lightroomDatasetBuild.status === "completed" && (lightroomDatasetBuild.manifest.invalid_pairs || 0) > 0 && (
                    <div className="datasetBuildNotice">
                      <strong>{(lightroomDatasetBuild.manifest.invalid_pairs || 0).toLocaleString()} תמונות לא נכנסו ל-Dataset</strong>
                      <span>ProGrapher לא מנחש התאמות. רק זוגות שנמצאו ואומתו נכנסים ללמידה.</span>
                    </div>
                  )}

                  {lightroomDatasetBuild.status === "completed" && (
                    <div className="datasetAuditBlock">
                      {!lightroomDatasetAudit || ["queued", "building"].includes(lightroomDatasetAudit.status) ? (
                        <div className="datasetAuditRunning">
                          <div className="datasetAuditSpinner" />
                          <div>
                            <span>בדיקת תקינות אוטומטית</span>
                            <strong>{lightroomDatasetAudit?.stage_he || "מאמתים את ה-Dataset לעומק"}</strong>
                            <p>בודקים כפילויות, דליפה בין ה-Splits, התאמה לסגנון שנבחר, Recipes וקבצי מקור.</p>
                          </div>
                          <em>{lightroomDatasetAudit?.progress_percent || 0}%</em>
                        </div>
                      ) : lightroomDatasetAudit.status === "failed" ? (
                        <div className="datasetAuditFailed">
                          <div>
                            <span>בדיקת התקינות נעצרה</span>
                            <strong>לא נסמן את ה-Dataset כמוכן לאימון</strong>
                            <p>{lightroomDatasetAudit.error || "אירעה שגיאה בבדיקת התקינות."}</p>
                          </div>
                          <button className="ghost" onClick={rerunLightroomDatasetAudit}>בדוק שוב</button>
                        </div>
                      ) : (
                        <>
                          <div className={`datasetAuditHero ${lightroomDatasetAudit.result.passed ? "passed" : "failed"}`}>
                            <div>
                              <span>Dataset Integrity</span>
                              <h3>{lightroomDatasetAudit.result.integrity_percent ?? 0}%</h3>
                              <strong>
                                {lightroomDatasetAudit.result.passed
                                  ? "ה-Dataset עבר את כל בדיקות התקינות הקריטיות"
                                  : "נמצאו בעיות שחייבים לפתור לפני אימון"}
                              </strong>
                            </div>
                            <div className="datasetAuditScoreRing">
                              <b>{lightroomDatasetAudit.result.checks_passed || 0}/{lightroomDatasetAudit.result.checks_total || 0}</b>
                              <small>בדיקות עברו</small>
                            </div>
                          </div>

                          <div className="datasetAuditChecks">
                            {(lightroomDatasetAudit.result.checks || []).map((check) => (
                              <div className={check.passed ? "passed" : "failed"} key={check.key}>
                                <i>{check.passed ? "✓" : "!"}</i>
                                <div>
                                  <strong>{check.label_he}</strong>
                                  {check.detail_he && <small>{check.detail_he}</small>}
                                </div>
                              </div>
                            ))}
                          </div>

                          {(lightroomDatasetAudit.result.preview || []).length > 0 && (
                            <details className="datasetAuditPreview">
                              <summary>הצג בדיקות מדגמיות מה-Dataset</summary>
                              <div className="datasetAuditPreviewGrid">
                                {(lightroomDatasetAudit.result.preview || []).map((sample) => {
                                  const recipeEntries = Object.entries(sample.develop_recipe || {}).slice(0, 4);
                                  return (
                                    <div key={sample.sample_id}>
                                      <strong>{sample.filename || "תמונה"}</strong>
                                      <span>{sample.style || "—"} · {(sample.split || "").toUpperCase()}</span>
                                      <small>
                                        {recipeEntries.length
                                          ? recipeEntries.map(([key, value]) => `${key}: ${String(value)}`).join(" · ")
                                          : "Recipe קיים"}
                                      </small>
                                    </div>
                                  );
                                })}
                              </div>
                            </details>
                          )}

                          <div className="datasetBuildNext integrityNext">
                            <div>
                              <span>השלב הבא</span>
                              <strong>
                                {lightroomDatasetAudit.result.passed
                                  ? "Dataset מאומת — ProGrapher עובר ל-Vision Brain"
                                  : "Dataset עדיין לא מוכן לאימון"}
                              </strong>
                              <p>
                                {lightroomDatasetAudit.result.passed
                                  ? "ה-Vision Brain מנתח את התמונות עצמן ומחבר לכל זוג embedding, הקשר חזותי ונתוני צילום. התהליך מתחיל אוטומטית."
                                  : "ProGrapher לא יתחיל אימון עד שכל הבדיקות הקריטיות יעברו."}
                              </p>
                            </div>
                            <span className="datasetLockedBadge">{(lightroomDatasetBuild.manifest.splits?.test || 0).toLocaleString()} TEST נעולים מחוץ לאימון</span>
                          </div>

                          {lightroomDatasetAudit.result.passed && (
                            <div className="profileAiPipeline">
                              <div className="profileAiSectionHead">
                                <div>
                                  <span>VISION BRAIN</span>
                                  <h3>מנתחים מה באמת קורה בכל תמונה</h3>
                                  <p>CLIP המקומי יוצר embedding והקשר חזותי לכל תמונה. ב-CUDA הוא משתמש בכרטיס המסך שלך.</p>
                                </div>
                                <div className={`profileAiStatus ${lightroomVisionJob?.status || "queued"}`}>
                                  {lightroomVisionJob?.status === "completed" ? "Vision מוכן" :
                                   lightroomVisionJob?.status === "failed" ? "Vision נעצר" :
                                   lightroomVisionJob?.stage === "queued" ? "מתחיל..." : "Vision עובד"}
                                </div>
                              </div>

                              {!lightroomVisionJob || ["queued", "building"].includes(lightroomVisionJob.status) ? (
                                <div className="profileAiProgress">
                                  <div className="profileAiProgressTop">
                                    <strong>{lightroomVisionJob?.stage_he || "מפעילים את Vision Brain"}</strong>
                                    <b>{lightroomVisionJob?.progress_percent || 0}%</b>
                                  </div>
                                  <div className="profileAiProgressTrack">
                                    <i style={{ width: `${Math.max(0, Math.min(100, lightroomVisionJob?.progress_percent || 0))}%` }} />
                                  </div>
                                  <div className="profileAiLiveStats">
                                    <div><span>נותחו</span><strong dir="ltr">{(lightroomVisionJob?.details?.processed || 0).toLocaleString()} / {(lightroomVisionJob?.details?.total || 5000).toLocaleString()}</strong></div>
                                    <div><span>TRAIN</span><strong>{(lightroomVisionJob?.details?.train_processed || 0).toLocaleString()}</strong></div>
                                    <div><span>VALIDATION</span><strong>{(lightroomVisionJob?.details?.validation_processed || 0).toLocaleString()}</strong></div>
                                    <div><span>TEST</span><strong>{(lightroomVisionJob?.details?.test_processed || 0).toLocaleString()}</strong></div>
                                    <div><span>מנוע</span><strong>{lightroomVisionJob?.details?.device?.toUpperCase() || (lightroomVisionJob?.stage === "warming_vision" ? "טוען..." : "—")}</strong></div>
                                  </div>
                                  {typeof lightroomVisionJob?.details?.eta_seconds === "number" && (
                                    <small className="profileAiEta">
                                      זמן משוער שנותר: {Math.max(1, Math.ceil((lightroomVisionJob.details.eta_seconds || 0) / 60))} דקות
                                    </small>
                                  )}
                                </div>
                              ) : lightroomVisionJob.status === "failed" ? (
                                <div className="profileAiError">
                                  <strong>ניתוח ה-Vision נעצר</strong>
                                  <p>{lightroomVisionJob.error || "אירעה שגיאה בניתוח התמונות."}</p>
                                  <button className="ghost" onClick={rebuildLightroomVisionJob}>נסה שוב</button>
                                </div>
                              ) : (
                                <div className="profileAiVisionReady">
                                  <div><span>תמונות שנותחו</span><strong>{(lightroomVisionJob.manifest.processed || 0).toLocaleString()}</strong></div>
                                  <div><span>Embedding</span><strong>{lightroomVisionJob.manifest.embedding_dimensions || 512}D</strong></div>
                                  <div><span>מנוע</span><strong>{lightroomVisionJob.manifest.device?.toUpperCase() || "—"}</strong></div>
                                  <div><span>מודל Vision</span><strong>CLIP</strong></div>
                                </div>
                              )}

                              {lightroomVisionJob?.status === "completed" && (
                                <div className="profileTrainingPanel">
                                  <div className="profileAiSectionHead">
                                    <div>
                                      <span>CONTEXT MODEL V1</span>
                                      <h3>עכשיו אפשר לאמן את המוח העריכתי</h3>
                                      <p>
                                        האימון משתמש רק ב-TRAIN וב-VALIDATION. קבוצת ה-TEST נשארת נעולה ונפתחת רק אחרי שהמודל הסופי ננעל.
                                      </p>
                                    </div>
                                  </div>

                                  {!lightroomTrainingRun && (
                                    <div className="profileTrainCta">
                                      <div>
                                        <strong>4,000 דוגמאות מוכנות לאימון</strong>
                                        <span>Vision + EXIF + Lightroom Recipe → מודל contextual אמיתי.</span>
                                      </div>
                                      <button
                                        className="primary profileTrainButton"
                                        onClick={startLightroomTraining}
                                        disabled={lightroomTrainingStarting}
                                      >
                                        {lightroomTrainingStarting ? "מתחיל אימון..." : "התחל אימון AI"}
                                      </button>
                                    </div>
                                  )}

                                  {lightroomTrainingRun && ["queued", "building"].includes(lightroomTrainingRun.status) && (
                                    <div className="profileAiProgress training">
                                      <div className="profileAiProgressTop">
                                        <strong>{lightroomTrainingRun.stage_he || "מאמנים את המודל"}</strong>
                                        <b>{lightroomTrainingRun.progress_percent || 0}%</b>
                                      </div>
                                      <div className="profileAiProgressTrack">
                                        <i style={{ width: `${Math.max(0, Math.min(100, lightroomTrainingRun.progress_percent || 0))}%` }} />
                                      </div>
                                      <p>
                                        {lightroomTrainingRun.stage === "testing_locked_set"
                                          ? "המודל כבר ננעל. עכשיו נפתחת לראשונה קבוצת ה-TEST לבדיקת אמת."
                                          : "המודל לומד את הקשר בין מה שהוא רואה בתמונה לבין החלטות העריכה של Expert C."}
                                      </p>
                                    </div>
                                  )}

                                  {lightroomTrainingRun?.status === "failed" && (
                                    <div className="profileAiError">
                                      <strong>האימון נעצר</strong>
                                      <p>{lightroomTrainingRun.error || "אירעה שגיאה באימון."}</p>
                                      <button className="primary" onClick={startLightroomTraining}>התחל אימון מחדש</button>
                                    </div>
                                  )}

                                  {lightroomTrainingRun?.status === "completed" && (
                                    <div className="profileTrainingResult">
                                      <div className="profileTrainingResultHero">
                                        <div>
                                          <span>MODEL READY</span>
                                          <h3>האימון הראשון של ProGrapher הושלם</h3>
                                          <p>
                                            {lightroomTrainingRun.metrics.model_type || "Context Model"} · {lightroomTrainingRun.metrics.target_count || 0} פרמטרים נלמדו · TEST נפתח רק לאחר נעילת המודל.
                                          </p>
                                        </div>
                                        <div className="profileModelBadge">V1</div>
                                      </div>

                                      <div className="profileMetricGrid">
                                        {Object.entries(lightroomTrainingRun.metrics.test || {}).map(([key, metric]) => {
                                          const typedMetric = metric as {
                                            mae?: number;
                                            improvement_percent?: number;
                                          };
                                          return (
                                            <div key={key}>
                                              <span>{key}</span>
                                              <strong>MAE {Number(typedMetric.mae || 0).toFixed(3)}</strong>
                                              <small>
                                                {Number(typedMetric.improvement_percent || 0) >= 0 ? "+" : ""}
                                                {Number(typedMetric.improvement_percent || 0).toFixed(1)}% מול baseline
                                              </small>
                                            </div>
                                          );
                                        })}
                                      </div>
                                      <div className="profileModelNote">
                                        זהו Context Model V1 ניסיוני. המדדים כאן אמיתיים מתוך 500 תמונות TEST שלא השתתפו באימון או בבחירת המודל.
                                      </div>
                                    </div>
                                  )}


                                  {lightroomTrainingRun?.status === "completed" && (
                                    <div className="evaluationLab">
                                      <div className="evaluationLabHead">
                                        <div>
                                          <span>EVALUATION LAB</span>
                                          <h3>בואו נראה איפה המודל באמת טוב — ואיפה הוא טועה</h3>
                                          <p>
                                            הניתוח מתבצע רק על 500 תמונות ה-TEST שנשארו נעולות עד לאחר סיום האימון.
                                          </p>
                                        </div>
                                        <button
                                          className="ghost"
                                          onClick={() => lightroomActiveProfileId && loadLightroomEvaluation(lightroomActiveProfileId, true)}
                                          disabled={lightroomEvaluationLoading}
                                        >
                                          {lightroomEvaluationLoading ? "מנתח..." : "חשב Evaluation מחדש"}
                                        </button>
                                      </div>

                                      {!lightroomEvaluation ? (
                                        <div className="evaluationLoading">
                                          <div className="miniSpinner" />
                                          <strong>{lightroomEvaluationLoading ? "מנתחים 500 תחזיות TEST..." : "טוענים Evaluation..."}</strong>
                                        </div>
                                      ) : (
                                        <>
                                          <div className="evaluationSummaryGrid">
                                            <div>
                                              <span>TEST אמיתי</span>
                                              <strong>{lightroomEvaluation.test_samples.toLocaleString()}</strong>
                                              <small>לא השתתף באימון</small>
                                            </div>
                                            <div>
                                              <span>פרמטרים שנלמדו</span>
                                              <strong>{lightroomEvaluation.trained_parameter_count}</strong>
                                              <small>{lightroomEvaluation.trained_parameters.join(" · ")}</small>
                                            </div>
                                            <div>
                                              <span>שיפור ממוצע מול baseline</span>
                                              <strong>
                                                {lightroomEvaluation.overall.mean_parameter_improvement_percent >= 0 ? "+" : ""}
                                                {lightroomEvaluation.overall.mean_parameter_improvement_percent.toFixed(1)}%
                                              </strong>
                                              <small>ממוצע בין הפרמטרים</small>
                                            </div>
                                            <div>
                                              <span>TEST נשאר נעול</span>
                                              <strong>{lightroomEvaluation.overall.test_was_locked ? "כן" : "לא"}</strong>
                                              <small>נפתח רק לאחר Model Lock</small>
                                            </div>
                                          </div>

                                          <div className="evaluationSection">
                                            <div className="evaluationSectionHead">
                                              <div>
                                                <span>PARAMETER ERROR</span>
                                                <h4>כמה המודל טועה בכל החלטת עריכה?</h4>
                                              </div>
                                            </div>
                                            <div className="evaluationParameterGrid">
                                              {Object.entries(lightroomEvaluation.parameter_stats).map(([key, stat]) => (
                                                <div key={key}>
                                                  <strong>{key}</strong>
                                                  <div className="evaluationMainMetric">MAE {Number(stat.mae).toFixed(3)}</div>
                                                  <div className="evaluationMetricRow">
                                                    <span>Median</span><b>{Number(stat.median_abs_error).toFixed(3)}</b>
                                                  </div>
                                                  <div className="evaluationMetricRow">
                                                    <span>P90</span><b>{Number(stat.p90_abs_error).toFixed(3)}</b>
                                                  </div>
                                                  <div className="evaluationMetricRow">
                                                    <span>Baseline</span><b>{Number(stat.baseline_mae).toFixed(3)}</b>
                                                  </div>
                                                  <small className={stat.improvement_percent >= 0 ? "positive" : "negative"}>
                                                    {stat.improvement_percent >= 0 ? "+" : ""}
                                                    {Number(stat.improvement_percent).toFixed(1)}% מול baseline
                                                  </small>
                                                </div>
                                              ))}
                                            </div>
                                          </div>

                                          <div className="evaluationSection">
                                            <div className="evaluationSectionHead">
                                              <div>
                                                <span>MODEL INPUT</span>
                                                <h4>על מה המודל הסתמך?</h4>
                                              </div>
                                            </div>
                                            <div className="evaluationInputImportance">
                                              <div>
                                                <span>Vision Embedding</span>
                                                <strong>{Number(lightroomEvaluation.feature_group_importance_percent.embedding || 0).toFixed(1)}%</strong>
                                              </div>
                                              <div>
                                                <span>EXIF / Metadata</span>
                                                <strong>{Number(lightroomEvaluation.feature_group_importance_percent.metadata || 0).toFixed(1)}%</strong>
                                              </div>
                                              <div>
                                                <span>Semantic Context</span>
                                                <strong>{Number(lightroomEvaluation.feature_group_importance_percent.semantic || 0).toFixed(1)}%</strong>
                                              </div>
                                            </div>
                                          </div>

                                          <div className="evaluationSection">
                                            <div className="evaluationSectionHead">
                                              <div>
                                                <span>TARGET COVERAGE</span>
                                                <h4>למה V1 למד רק חלק מהפקדים?</h4>
                                              </div>
                                            </div>
                                            <div className="evaluationCoverageGrid">
                                              {Object.entries(lightroomEvaluation.coverage).map(([key, item]) => (
                                                <div className={item.trained ? "trained" : "missing"} key={key}>
                                                  <div>
                                                    <strong>{key}</strong>
                                                    <span>{item.train_coverage_percent.toFixed(1)}% coverage ב-TRAIN</span>
                                                  </div>
                                                  <em>
                                                    {item.trained
                                                      ? "נלמד"
                                                      : item.reason === "insufficient_target_coverage"
                                                        ? "אין מספיק Targets"
                                                        : "לא נכנס ל-V1"}
                                                  </em>
                                                </div>
                                              ))}
                                            </div>
                                          </div>

                                          <div className="evaluationSection">
                                            <div className="evaluationSectionHead sampleHead">
                                              <div>
                                                <span>PREDICTION INSPECTOR</span>
                                                <h4>500 תחזיות — אחת מול אחת מול Expert C</h4>
                                              </div>
                                              <div className="evaluationTabs">
                                                <button
                                                  className={evaluationSampleMode === "worst" ? "active" : ""}
                                                  onClick={() => setEvaluationSampleMode("worst")}
                                                >
                                                  הטעויות הגדולות
                                                </button>
                                                <button
                                                  className={evaluationSampleMode === "best" ? "active" : ""}
                                                  onClick={() => setEvaluationSampleMode("best")}
                                                >
                                                  הכי מדויקות
                                                </button>
                                                <button
                                                  className={evaluationSampleMode === "representative" ? "active" : ""}
                                                  onClick={() => setEvaluationSampleMode("representative")}
                                                >
                                                  מדגם
                                                </button>
                                              </div>
                                            </div>

                                            {(() => {
                                              const pool =
                                                evaluationSampleMode === "worst"
                                                  ? lightroomEvaluation.worst_samples
                                                  : evaluationSampleMode === "best"
                                                    ? lightroomEvaluation.best_samples
                                                    : lightroomEvaluation.representative_samples;
                                              const selected =
                                                pool.find((sample) => sample.sample_id === evaluationSelectedSampleId) ||
                                                pool[0];

                                              return (
                                                <div className="predictionInspector">
                                                  <div className="predictionSampleList">
                                                    {pool.map((sample) => (
                                                      <button
                                                        key={sample.sample_id}
                                                        className={selected?.sample_id === sample.sample_id ? "active" : ""}
                                                        onClick={() => setEvaluationSelectedSampleId(sample.sample_id)}
                                                      >
                                                        <strong>{sample.filename}</strong>
                                                        <span>Relative error ×{sample.composite_normalized_error.toFixed(2)}</span>
                                                      </button>
                                                    ))}
                                                  </div>

                                                  {selected && (
                                                    <div className="predictionSampleDetail">
                                                      <div className="predictionSampleTitle">
                                                        <div>
                                                          <span>TEST SAMPLE</span>
                                                          <h5>{selected.filename}</h5>
                                                        </div>
                                                        <strong>×{selected.composite_normalized_error.toFixed(2)}</strong>
                                                      </div>

                                                      <div className="predictionCompareTable">
                                                        <div className="predictionCompareHeader">
                                                          <span>פרמטר</span>
                                                          <span>Expert C</span>
                                                          <span>ProGrapher</span>
                                                          <span>שגיאה</span>
                                                        </div>
                                                        {Object.entries(selected.parameters).map(([key, value]) => (
                                                          <div className="predictionCompareRow" key={key}>
                                                            <strong>{key}</strong>
                                                            <span>{Number(value.actual).toFixed(2)}</span>
                                                            <span>{Number(value.predicted).toFixed(2)}</span>
                                                            <span>{Number(value.abs_error).toFixed(2)}</span>
                                                          </div>
                                                        ))}
                                                      </div>

                                                      <div className="predictionContext">
                                                        <span>ISO {selected.metadata.iso || "—"}</span>
                                                        <span>f/{selected.metadata.aperture || "—"}</span>
                                                        <span>{selected.metadata.focal_length || "—"}mm</span>
                                                        <span>{selected.metadata.camera_model || "Camera —"}</span>
                                                      </div>
                                                    </div>
                                                  )}
                                                </div>
                                              );
                                            })()}
                                          </div>
                                        </>
                                      )}
                                    </div>
                                  )}


                                  {lightroomTrainingRun?.status === "completed" && (
                                    <div className="recipeV2Lab">
                                      <div className="evaluationLabHead">
                                        <div>
                                          <span>RECIPE INTELLIGENCE V2</span>
                                          <h3>עכשיו משפרים את ה-Targets — בלי לשנות את ה-Vision</h3>
                                          <p>
                                            ProGrapher קורא מחדש את הגדרות Lightroom, מזהה Process Version,
                                            משלים רק ברירות מחדל חוקיות ומאמן Temperature בצורה יציבה יותר.
                                          </p>
                                        </div>
                                        <button
                                          className="ghost"
                                          onClick={() => lightroomActiveProfileId && loadRecipeV2(lightroomActiveProfileId, true)}
                                          disabled={recipeV2Loading}
                                        >
                                          {recipeV2Loading ? "מנתח..." : "נתח Recipe מחדש"}
                                        </button>
                                      </div>

                                      {!recipeV2Report ? (
                                        <div className="evaluationLoading">
                                          <div className="miniSpinner" />
                                          <strong>{recipeV2Loading ? "מנתחים את Lightroom Recipes..." : "טוענים Recipe Intelligence..."}</strong>
                                        </div>
                                      ) : (
                                        <>
                                          <div className="recipeV2Summary">
                                            <div>
                                              <span>Legacy Process</span>
                                              <strong>{recipeV2Report.process_family_counts.legacy.toLocaleString()}</strong>
                                            </div>
                                            <div>
                                              <span>Modern Process</span>
                                              <strong>{recipeV2Report.process_family_counts.modern.toLocaleString()}</strong>
                                            </div>
                                            <div>
                                              <span>Unknown</span>
                                              <strong>{recipeV2Report.process_family_counts.unknown.toLocaleString()}</strong>
                                            </div>
                                            <div>
                                              <span>White Balance V2</span>
                                              <strong>Mired</strong>
                                              <small>מוחזר ל-Kelvin בתוצאה</small>
                                            </div>
                                          </div>

                                          <div className="evaluationSection">
                                            <div className="evaluationSectionHead">
                                              <div>
                                                <span>TARGET RECOVERY</span>
                                                <h4>כמה מידע הצלחנו לשחזר לעומת V1?</h4>
                                              </div>
                                            </div>

                                            <div className="recipeCoverageTable">
                                              <div className="recipeCoverageHeader">
                                                <span>פרמטר</span>
                                                <span>V1</span>
                                                <span>V2</span>
                                                <span>מצב</span>
                                              </div>
                                              {Object.entries(recipeV2Report.coverage).map(([key, item]) => (
                                                <div className="recipeCoverageRow" key={key}>
                                                  <strong>{key}</strong>
                                                  <span>{item.v1_percent_all_splits.toFixed(1)}%</span>
                                                  <span>{item.v2_percent_all_splits.toFixed(1)}%</span>
                                                  {(() => {
                                                    const decision = recipeV2Report.learnability?.[key];
                                                    const status = decision?.status || (item.train_eligible ? "trainable" : "unsupported");
                                                    return (
                                                      <em className={`targetDecision ${status}`}>
                                                        {status === "trainable"
                                                          ? "מוכן ללמידה"
                                                          : status === "constant"
                                                            ? `קבוע ${decision?.constant_value ?? ""}`
                                                            : status === "sparse"
                                                              ? "Sparse — מוחרג"
                                                              : status === "suspicious"
                                                                ? "חשוד — מוחרג"
                                                                : "לא נתמך מספיק"}
                                                      </em>
                                                    );
                                                  })()}
                                                </div>
                                              ))}
                                            </div>
                                          </div>

                                          <div className="evaluationSection targetGuardSection">
                                            <div className="evaluationSectionHead">
                                              <div>
                                                <span>TARGET PROVENANCE & LEARNABILITY</span>
                                                <h4>מה באמת שווה ללמד — ומה לא נכנס למודל</h4>
                                              </div>
                                            </div>

                                            <div className="targetGuardSummary">
                                              <div className="trainable">
                                                <span>Trainable</span>
                                                <strong>{recipeV2Report.guard.trainable_count}</strong>
                                              </div>
                                              <div className="constant">
                                                <span>Constant</span>
                                                <strong>{recipeV2Report.guard.constant_count}</strong>
                                              </div>
                                              <div className="sparse">
                                                <span>Sparse</span>
                                                <strong>{recipeV2Report.guard.sparse_count}</strong>
                                              </div>
                                              <div className="suspicious">
                                                <span>Suspicious</span>
                                                <strong>{recipeV2Report.guard.suspicious_count}</strong>
                                              </div>
                                              <div className="unsupported">
                                                <span>Unsupported</span>
                                                <strong>{recipeV2Report.guard.unsupported_count}</strong>
                                              </div>
                                            </div>

                                            <div className="targetProvenanceTable">
                                              <div className="targetProvenanceHeader">
                                                <span>פרמטר</span>
                                                <span>מקור עיקרי</span>
                                                <span>Explicit</span>
                                                <span>Default</span>
                                                <span>V1 fallback</span>
                                                <span>Variation</span>
                                                <span>החלטה</span>
                                              </div>

                                              {Object.entries(recipeV2Report.learnability).map(([key, decision]) => {
                                                const source = recipeV2Report.provenance?.[key];
                                                return (
                                                  <div className="targetProvenanceRow" key={key}>
                                                    <strong>{key}</strong>
                                                    <span className="sourceName">{decision.top_source || "—"}</span>
                                                    <span>{decision.explicit_percent_train.toFixed(1)}%</span>
                                                    <span>{decision.default_percent_train.toFixed(1)}%</span>
                                                    <span>{decision.v1_fallback_percent_train.toFixed(1)}%</span>
                                                    <span>
                                                      {decision.unique_value_count_train} values
                                                      <small>
                                                        support {decision.variation_support_count_train ?? 0}
                                                        /{decision.minimum_variation_support_required ?? 0}
                                                        {" "}· Δ {Number(decision.value_range_train || 0).toFixed(2)}
                                                      </small>
                                                    </span>
                                                    <em className={`targetDecision ${decision.status}`}>
                                                      {decision.status === "trainable"
                                                        ? "TRAIN"
                                                        : decision.status === "constant"
                                                          ? `CONST ${decision.constant_value ?? ""}`
                                                          : decision.status === "sparse"
                                                            ? "SPARSE"
                                                            : decision.status === "suspicious"
                                                              ? "EXCLUDED"
                                                              : "SKIP"}
                                                    </em>
                                                  </div>
                                                );
                                              })}
                                            </div>

                                            {Object.entries(recipeV2Report.learnability)
                                              .filter(([, item]) => item.status === "sparse")
                                              .map(([key, item]) => (
                                                <div className="targetGuardWarning sparseWarning" key={key}>
                                                  <strong>{key} דל מדי ללמידה</strong>
                                                  <span>
                                                    קיימות רק {item.variation_support_count_train ?? 0} דוגמאות ששונות מהערך הדומיננטי,
                                                    כאשר ה-Guard דורש לפחות {item.minimum_variation_support_required ?? 0}.
                                                    ה-Target נשמר בדוח אך לא נכנס ל-Context Model V2.
                                                  </span>
                                                </div>
                                              ))}

                                            {Object.entries(recipeV2Report.learnability)
                                              .filter(([, item]) => item.status === "suspicious")
                                              .map(([key, item]) => (
                                                <div className="targetGuardWarning" key={key}>
                                                  <strong>{key} הוחרג מהאימון</strong>
                                                  <span>
                                                    מקור: {item.top_source || "לא ידוע"} ·
                                                    בקטלוג Legacy השדה הזה אינו בטוח כפקד Basic מודרני.
                                                    ProGrapher לא ילמד אותו עד שנוכיח את ה-Provenance שלו.
                                                  </span>
                                                </div>
                                              ))}

                                            {Object.keys(recipeV2Report.constant_profile_values || {}).length > 0 && (
                                              <div className="constantTargetsBox">
                                                <strong>Constants נשמרים בפרופיל בלי לאמן מודל מיותר</strong>
                                                <div>
                                                  {Object.entries(recipeV2Report.constant_profile_values).map(([key, value]) => (
                                                    <span key={key}>{key} = {Number(value).toFixed(2)}</span>
                                                  ))}
                                                </div>
                                              </div>
                                            )}
                                          </div>

                                          <div className="evaluationSection">
                                            <div className="evaluationSectionHead">
                                              <div>
                                                <span>TARGET SANITY</span>
                                                <h4>התפלגות Targets — extremes נשמרים ולא נמחקים</h4>
                                              </div>
                                            </div>
                                            <div className="recipeDistributionGrid">
                                              {Object.entries(recipeV2Report.distributions)
                                                .filter(([, dist]) => dist.count > 0)
                                                .map(([key, dist]) => (
                                                  <div key={key}>
                                                    <strong>{key}</strong>
                                                    <div><span>Median</span><b>{dist.median == null ? "—" : Number(dist.median).toFixed(2)}</b></div>
                                                    <div><span>P99</span><b>{dist.p99 == null ? "—" : Number(dist.p99).toFixed(2)}</b></div>
                                                    <div><span>Max</span><b>{dist.max == null ? "—" : Number(dist.max).toFixed(2)}</b></div>
                                                    <small>{dist.extreme_count} extreme samples נשמרו</small>
                                                  </div>
                                                ))}
                                            </div>
                                          </div>

                                          {!trainingV2Run && (
                                            <div className="profileTrainCta recipeV2Cta">
                                              <div>
                                                <strong>Target Guard עבר — מאמנים רק Targets מאומתים ומשתנים</strong>
                                                <span>
                                                  {recipeV2Report.guard.trainable_count} Targets ילמדו ·
                                                  {" "}{recipeV2Report.guard.constant_count} Constants נשמרים ללא מודל ·
                                                  {" "}{recipeV2Report.guard.sparse_count} Sparse מוחרגים ·
                                                  {" "}{recipeV2Report.guard.suspicious_count} Suspicious מוחרגים.
                                                </span>
                                              </div>
                                              <button
                                                className="primary profileTrainButton"
                                                onClick={startTrainingV2}
                                                disabled={trainingV2Starting || !recipeV2Report.guard.ready_for_training}
                                              >
                                                {trainingV2Starting ? "מתחיל V2..." : "אמן Context Model V2 — Targets מאומתים בלבד"}
                                              </button>
                                            </div>
                                          )}

                                          {trainingV2Run && ["queued", "building"].includes(trainingV2Run.status) && (
                                            <div className="profileAiProgress training recipeV2Progress">
                                              <div className="profileAiProgressTop">
                                                <strong>{trainingV2Run.stage_he || "מאמנים Context Model V2"}</strong>
                                                <b>{trainingV2Run.progress_percent || 0}%</b>
                                              </div>
                                              <div className="profileAiProgressTrack">
                                                <i style={{ width: `${Math.max(0, Math.min(100, trainingV2Run.progress_percent || 0))}%` }} />
                                              </div>
                                              <p>
                                                V2 משתמש באותם 4,000 TRAIN ובאותם 500 VALIDATION.
                                                ה-TEST נפתח רק לאחר נעילת V2.
                                              </p>
                                            </div>
                                          )}

                                          {trainingV2Run?.status === "failed" && (
                                            <div className="profileAiError">
                                              <strong>אימון V2 נעצר</strong>
                                              <p>{trainingV2Run.error || "אירעה שגיאה באימון Recipe V2."}</p>
                                              <button className="primary" onClick={startTrainingV2}>התחל V2 מחדש</button>
                                            </div>
                                          )}

                                          {trainingV2Run?.status === "completed" && (
                                            <div className="v2Comparison">
                                              <div className="profileTrainingResultHero">
                                                <div>
                                                  <span>{trainingV2Run.metrics.pipeline_version || "V1 vs V2"}</span>
                                                  <h3>השוואה על אותו TEST בדיוק</h3>
                                                  <p>
                                                    ערך חיובי אומר ש-V2 הקטין את ה-MAE לעומת V1.
                                                    פרמטר חדש מסומן כ-New.
                                                  </p>
                                                </div>
                                                <div className="profileModelBadge">V2</div>
                                              </div>

                                              <div className="v2CompareTable">
                                                <div className="v2CompareHeader">
                                                  <span>פרמטר</span>
                                                  <span>V1 MAE</span>
                                                  <span>V2 MAE</span>
                                                  <span>שינוי</span>
                                                </div>
                                                {Object.entries(trainingV2Run.metrics.v1_vs_v2 || {}).map(([key, item]) => (
                                                  <div className="v2CompareRow" key={key}>
                                                    <strong>{key}</strong>
                                                    <span>{item.v1_mae == null ? "—" : Number(item.v1_mae).toFixed(3)}</span>
                                                    <span>{Number(item.v2_mae || 0).toFixed(3)}</span>
                                                    <em className={
                                                      item.new_in_v2
                                                        ? "new"
                                                        : Number(item.v2_vs_v1_improvement_percent || 0) >= 0
                                                          ? "better"
                                                          : "worse"
                                                    }>
                                                      {item.new_in_v2
                                                        ? "NEW"
                                                        : `${Number(item.v2_vs_v1_improvement_percent || 0) >= 0 ? "+" : ""}${Number(item.v2_vs_v1_improvement_percent || 0).toFixed(1)}%`}
                                                    </em>
                                                  </div>
                                                ))}
                                              </div>
                                            </div>
                                          )}
                                        </>
                                      )}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </section>
              )}

              <section className="styleDnaHero panel">
                <div className="styleDnaHeroMain">
                  <div
                    className="styleDnaScore"
                    style={{
                      background: `conic-gradient(#7aa7ff ${styleDna?.confidence_percent || 0}%, rgba(255,255,255,.06) 0)`,
                    }}
                  >
                    <div>
                      <strong>{styleDna ? `${styleDna.confidence_percent}%` : "—"}</strong>
                      <span>רמת למידה</span>
                    </div>
                  </div>

                  <div>
                    <div className="eyebrow">מפת הסגנון האישית</div>
                    <h2>ProGrapher לומד מההחלטות שלך</h2>
                    <p>
                      {styleDna?.status_he ||
                        "ממתין למשוב ראשון כדי להתחיל לבנות את הסגנון שלך."}
                    </p>
                  </div>
                </div>

                <div className="styleLearningStrength">
                  <span>עוצמת ההשפעה על תמונות חדשות</span>
                  <strong>{styleDna ? `${styleDna.learning_strength_percent}%` : "0%"}</strong>
                  <div className="styleStrengthBar">
                    <i style={{ width: `${styleDna?.learning_strength_percent || 0}%` }} />
                  </div>
                </div>
              </section>

              <section className="eventStats styleStats">
                <SmallStat label="החלטות שנלמדו" value={String(styleDna?.sample_count ?? 0)} />
                <SmallStat label="אושרו ללא תיקון" value={String(styleDna?.approval_count ?? 0)} />
                <SmallStat label="תוקנו ידנית" value={String(styleDna?.correction_count ?? 0)} />
                <SmallStat
                  label="קבלה ללא תיקון"
                  value={stats?.acceptance_rate != null ? `${stats.acceptance_rate}%` : "—"}
                />
              </section>

              <section className="styleInsightPanel"><div className="styleInsightGlow" aria-hidden="true"/><div className="styleInsightCopy"><span>פענוח סגנון</span><h3>{styleNarrative.title}</h3><p>{styleNarrative.body}</p>{styleNarrative.bullets.length>0&&<div className="styleInsightTags">{styleNarrative.bullets.map((item)=><span key={item}>{item}</span>)}</div>}</div><div className="styleInsightConfidence"><strong>{styleDna?.confidence_percent ?? 0}%</strong><span>ביטחון בפענוח</span></div></section>

              <section className="twoColumns styleLearningColumns">
                <div className="panel">
                  <div className="panelTitle">מה ProGrapher למד על העריכה שלך</div>

                  {!styleDna || styleDna.sample_count === 0 ? (
                    <div className="emptyState">
                      עדיין אין נתוני למידה. ערוך תמונה, בחר אישור או בצע תיקון ידני —
                      ומפת הסגנון תתחיל להיבנות.
                    </div>
                  ) : styleDna.top_adjustments.length === 0 ? (
                    <div className="notice">
                      <strong>העריכות הראשונות תואמות להצעות המנוע</strong>
                      כרגע לא זוהתה הטיה קבועה בפרמטרים. גם זו למידה חשובה.
                    </div>
                  ) : (
                    <div className="styleBiasList">
                      {styleDna.top_adjustments.map((item) => (
                        <div className="styleBiasRow" key={item.key}>
                          <div>
                            <strong>{item.label}</strong>
                            <span>התאמה אוטומטית לתמונות חדשות</span>
                          </div>
                          <b className={item.bias > 0 ? "positive" : "negative"}>
                            {item.bias > 0 ? "+" : ""}
                            {roundDisplay(item.bias)}
                          </b>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="panel">
                  <div className="panelTitle">איך הלמידה עובדת</div>
                  <div className="learningSteps">
                    <div>
                      <span>1</span>
                      <p><strong>אישור</strong> מלמד שהמתכון שקיבלת היה נכון.</p>
                    </div>
                    <div>
                      <span>2</span>
                      <p><strong>תיקון ידני</strong> מלמד בדיוק כמה היית משנה כל פרמטר.</p>
                    </div>
                    <div>
                      <span>3</span>
                      <p>בתמונה חדשה ההעדפות שנלמדו מתווספות למתכון הבסיס.</p>
                    </div>
                  </div>

                  <div className="styleSafetyNote">
                    בתחילת הדרך ההשפעה בכוונה חלשה. אחרי 8 החלטות היא מגיעה לעוצמה מלאה,
                    כדי שתמונה אחת לא תשנה בטעות את כל הסגנון.
                  </div>
                </div>
              </section>
            </>
          )}

          {view === "profile" && (
            <>
              <section className="profileHero panel">
                <div className="profileHeroMain">
                  <div className="bigAvatar">מ</div>
                  <div>
                    <h2>הפרופיל שלי</h2>
                    <p>הפרטים האישיים וסביבת העבודה.</p>
                  </div>
                </div>

                <div className="profileHeroActions">
                  <button className="ghost" onClick={() => navigate("style")}>מעבר לפרופיל הסגנון</button>
                  <button className="primary" onClick={() => { setProfileSaved(true); setTimeout(() => setProfileSaved(false), 2200); }}>
                    שמירת הפרופיל
                  </button>
                </div>
              </section>

              {profileSaved && <div className="saveToast">הפרופיל נשמר בהצלחה</div>}

              <section className="profileGrid">
                <div className="panel">
                  <div className="panelTitle">פרטים אישיים</div>
                  <div className="formGrid">
                    <label>שם מלא<input defaultValue="מתן" /></label>
                    <label>שם הסטודיו / העסק<input placeholder="שם הסטודיו" /></label>
                  </div>
                </div>

                <div className="panel">
                  <div className="panelTitle">סביבת העבודה</div>
                  <div className="profileInfoRows">
                    <InfoRow label="מצב המנוע" value={engineOnline ? "מחובר" : "מנותק"} />
                    <InfoRow label="RAW" value={system?.raw_support ? "פעיל" : "—"} />
                    <InfoRow label="EXIF" value={system?.exif_support ? "פעיל" : "—"} />
                    <InfoRow label="GPU" value={system?.gpu?.available ? system.gpu.name || "זוהה" : "—"} />
                  </div>
                </div>
              </section>

              <section className="profileAdvanced panel">
                <div>
                  <span>כלים מתקדמים</span>
                  <strong>מערכת ואבחון</strong>
                  <p>כלי מערכת ונתוני מחקר הופרדו מחוויית העבודה הרגילה.</p>
                </div>
                <div>
                  <button className="ghost" onClick={() => navigate("system")}>נתוני מערכת</button>
                  <button className="ghost" onClick={() => navigate("diagnostics")}>אבחון AI למפתחים</button>
                </div>
              </section>
            </>
          )}

          {view === "review" && (
            <section className="reviewLayout">
              <div className="compareBox">
                <div className="beforeSide" />
                <div className="afterSide" style={{ clipPath: `inset(0 0 0 ${compare}%)` }} />
                <div className="compareLine" style={{ left: `${compare}%` }} />
                <div className="beforeBadge">מקור</div>
                <div className="afterBadge">עריכה</div>
              </div>

              <aside className="panel reviewTools">
                <div className="panelTitle">התאמות</div>
                <Slider label="חשיפה" value="+0.20" initial={58} />
                <Slider label="טמפרטורה" value="-120" initial={44} />
                <Slider label="קונטרסט" value="+18" initial={61} />
              </aside>
            </section>
          )}

          {view === "lab" && (
            <section className="twoColumns">
              <div className="panel">
                <div className="panelTitle">מעבדת עריכה</div>
                <div className="emptyState">כאן תגיע בקרוב גם שליטת Recipe ידנית.</div>
              </div>
              <div className="panel">
                <div className="panelTitle">המיילסטון הבא</div>
                <div className="notice">
                  <strong>Closed Loop פעיל</strong>
                  עריכות, אישורים, תיקונים, למידה וייצוא כבר מחוברים מקצה לקצה.
                </div>
              </div>
            </section>
          )}

          {view === "system" && (
            <>
              <section className="systemPageHead panel">
                <div>
                  <span>ADVANCED</span>
                  <h2>נתוני מערכת</h2>
                  <p>בדיקת תחנת העבודה המקומית. אין צורך להיכנס לכאן במהלך עבודה רגילה.</p>
                </div>
                <div>
                  <button className="ghost" onClick={() => navigate("profile")}>חזרה לפרופיל</button>
                  <button className="ghost" onClick={() => navigate("diagnostics")}>אבחון AI מתקדם</button>
                </div>
              </section>
              <section className="systemGrid">
              <SystemCard title="כרטיס מסך" value={system?.gpu?.available ? system.gpu.name || "זוהה" : "—"} percent={system?.gpu?.utilization_percent ?? 0} />
              <SystemCard title="זיכרון מערכת" value={system?.ram?.percent != null ? `${system.ram.percent}% בשימוש` : "—"} percent={system?.ram?.percent ?? 0} />
              <SystemCard title="מעבד" value={system?.cpu?.percent != null ? `${system.cpu.percent}% בשימוש` : "—"} percent={system?.cpu?.percent ?? 0} />
              <SystemCard title="RAW" value={system?.raw_support ? "פעיל" : "—"} percent={system?.raw_support ? 100 : 0} />
              <SystemCard title="EXIF" value={system?.exif_support ? "פעיל" : "—"} percent={system?.exif_support ? 100 : 0} />
              <SystemCard title="חיבור מנוע" value={engineOnline ? "מחובר" : "מנותק"} percent={engineOnline ? 100 : 0} />
              </section>
            </>
          )}
        </main>
      </section>

      <div className="toastStack" aria-live="polite" aria-atomic="true">
        {successMessage && (
          <div className="appToast successToast">
            <span className="toastIcon" aria-hidden="true">✓</span>
            <div className="toastText">
              <strong>הפעולה הושלמה</strong>
              <span>{successMessage}</span>
            </div>
            <button onClick={() => setSuccessMessage("")} aria-label="סגור התראה">×</button>
          </div>
        )}

        {engineError && (
          <div className="appToast errorToast">
            <span className="toastIcon" aria-hidden="true">!</span>
            <div className="toastText">
              <strong>{engineOnline === false ? "המנוע המקומי לא מחובר" : "משהו לא הסתדר"}</strong>
              <span>{engineError}</span>
            </div>
            <button onClick={() => setEngineError("")} aria-label="סגור התראה">×</button>
          </div>
        )}
      </div>

      {deleteTarget && (
        <div className="deleteModalBackdrop" onMouseDown={() => !deletingEvent && setDeleteTarget(null)}>
          <div className="deleteModal" onMouseDown={(e) => e.stopPropagation()}>
            <div className="deleteModalIcon">!</div>
            <h3>למחוק את האירוע?</h3>
            <p>
              <strong>{deleteTarget.name}</strong> וכל התמונות, ה־Previews, העריכות,
              הניתוחים וה־AI embeddings שלו יימחקו מהמחשב לצמיתות.
            </p>

            <label className="preserveLearningOption">
              <input
                type="checkbox"
                checked={keepLearningOnDelete}
                onChange={(e) => setKeepLearningOnDelete(e.target.checked)}
                disabled={deletingEvent}
              />
              <span>
                <strong>שמור רק את הלמידה של סגנון הצלם</strong>
                <small>
                  נשמור את ההבדל בין הצעת ה־AI לעריכה שאושרה/תוקנה.
                  התמונות וה־Metadata עצמם לא נשמרים.
                </small>
              </span>
            </label>

            <div className="deleteModalActions">
              <button
                className="ghost"
                onClick={() => setDeleteTarget(null)}
                disabled={deletingEvent}
              >
                ביטול
              </button>
              <button
                className="confirmDeleteButton"
                onClick={confirmDeleteEvent}
                disabled={deletingEvent}
              >
                {deletingEvent ? "מוחק..." : "מחק אירוע לצמיתות"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


function StyleSetupStage({
  label,
  done,
  active,
  detail,
}: {
  label: string;
  done: boolean;
  active: boolean;
  detail: string;
}) {
  return (
    <div className={`styleSetupStage ${done ? "done" : ""} ${active ? "active" : ""}`}>
      <i>{done ? "✓" : active ? "•" : ""}</i>
      <strong>{label}</strong>
      <span>{detail}</span>
    </div>
  );
}

function LocalImage({
  url,
  alt,
  className,
  style,
}: {
  url: string;
  alt: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    setFailed(false);
    setSrc(null);

    fetch(url, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error("Preview failed");
        return response.blob();
      })
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => {
        if (active) setFailed(true);
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  if (failed) return <div className={`noPreview ${className || ""}`}>לא ניתן לטעון Preview</div>;
  if (!src) return <div className={`previewLoading ${className || ""}`}>טוען...</div>;
  return <img className={className} style={style} src={src} alt={alt} draggable={false} />;
}

function MetadataRows({ metadata }: { metadata?: PhotoMetadata }) {
  return (
    <div className="metadataRows">
      <InfoRow label="מצלמה" value={cameraLabel(metadata)} />
      <InfoRow label="עדשה" value={metadata?.lens || "—"} />
      <InfoRow label="ISO" value={metadata?.iso || "—"} />
      <InfoRow label="צמצם" value={metadata?.aperture || "—"} />
      <InfoRow label="מהירות תריס" value={metadata?.shutter_speed || "—"} />
      <InfoRow label="אורך מוקד" value={metadata?.focal_length || "—"} />
      <InfoRow label="תאריך צילום" value={metadata?.date_taken || "—"} />
    </div>
  );
}

function cameraLabel(metadata?: PhotoMetadata) {
  const parts = [metadata?.camera_make, metadata?.camera_model].filter(Boolean);
  return parts.length ? parts.join(" ") : "מצלמה לא זוהתה";
}

function resolutionLabel(photo: ApiPhoto) {
  const width = photo.metadata?.width || photo.width;
  const height = photo.metadata?.height || photo.height;
  return width && height ? `${width} × ${height}` : "—";
}

function formatBytes(bytes: number) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function photoStatusLabel(value?: string | null) {
  if (!value) return "מוכן";
  const normalized = value.toLowerCase();
  if (normalized === "rendered") return "ערוך";
  if (normalized === "corrected") return "תוקן";
  return value;
}

function formatDateTime(value: string) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("he-IL");
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="panel statCard"><span>{label}</span><strong>{value}</strong></div>;
}

function SmallStat({ label, value }: { label: string; value: string }) {
  return <div className="panel smallStat"><span>{label}</span><strong>{value}</strong></div>;
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return <div className="miniStat"><span>{label}</span><strong>{value}</strong></div>;
}

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return <div className="sectionHeader"><h2>{title}</h2><p>{subtitle}</p></div>;
}

function Slider({ label, value, initial }: { label: string; value: string; initial: number }) {
  return (
    <div className="sliderRow">
      <label>{label}</label>
      <input type="range" defaultValue={initial} />
      <span>{value}</span>
    </div>
  );
}

function SystemCard({ title, value, percent }: { title: string; value: string; percent: number }) {
  return (
    <div className="panel systemCard">
      <span>{title}</span>
      <strong>{value}</strong>
      <div className="systemBar">
        <i style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="infoRow">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DarkroomSlider({
  label,
  value,
  aiValue,
  min,
  max,
  step,
  track = "neutral",
  disabled = false,
  unit = "",
  signed = true,
  showNeutral = true,
  neutralValue = 0,
  onChange,
}: {
  label: string;
  value: number;
  aiValue: number;
  min: number;
  max: number;
  step: number;
  track?: "neutral" | "temperature" | "exposure" | "contrast" | "highlights" | "shadows" | "whites" | "blacks" | "clarity" | "vibrance";
  disabled?: boolean;
  unit?: string;
  signed?: boolean;
  showNeutral?: boolean;
  neutralValue?: number;
  onChange: (value: number) => void;
}) {
  const displayNumber = (input: number) => {
    const raw = roundDisplay(input);
    const prefix = signed && input > 0 ? "+" : "";
    return `${prefix}${raw}${unit}`;
  };
  const formattedValue = displayNumber(value);
  const formattedAi = displayNumber(aiValue);
  const changed = Math.abs(Number(value) - Number(aiValue)) > 0.0001;
  const neutralPercent = Math.max(
    0,
    Math.min(100, ((neutralValue - min) / Math.max(0.000001, max - min)) * 100)
  );

  return (
    <div className={`darkroomSlider track-${track} ${changed ? "changed" : ""} ${disabled ? "disabled" : ""}`}>
      <div className="darkroomSliderTop">
        <span>{label}</span>
        <div>
          {changed && <small>AI {formattedAi}</small>}
          <strong>{formattedValue}</strong>
        </div>
      </div>
      <div className="darkroomRangeShell">
        {showNeutral && (
          <span className="darkroomRangeCenter" style={{ left: `${neutralPercent}%` }} />
        )}
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onDoubleClick={() => !disabled && onChange(aiValue)}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      </div>
    </div>
  );
}

function CorrectionSlider({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="correctionSlider">
      <div className="correctionSliderTop">
        <span>{label}</span>
        <strong>{value > 0 ? `+${roundDisplay(value)}` : roundDisplay(value)}</strong>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function buildStyleNarrative(dna: StyleDnaSummary | null, onboarding: OnboardingProfile) {
  const stated = onboarding.style_words.length ? `בתיאור הראשוני שלך סימנת שאתה מתחבר ל־${onboarding.style_words.slice(0,3).join(", ")}.` : "";
  if (!dna || dna.sample_count === 0) return { title: "עדיין בונים את החתימה שלך", body: `${stated} כרגע אין מספיק החלטות עריכה בפועל כדי להסיק איך ההעדפות האלה מתבטאות בתמונות. אחרי כמה אישורים ותיקונים נתחיל להשוות בין מה שאמרת למה שאתה באמת עושה.`, bullets: onboarding.priorities.slice(0,3) };
  const o:string[]=[]; const b=dna.bias;
  if ((b.highlights||0)<-2) o.push("אתה נוטה להגן יותר על אזורים בהירים");
  if ((b.shadows||0)>2) o.push("אתה אוהב לפתוח מעט את הצללים");
  if ((b.contrast||0)>2) o.push("יש נטייה לקונטרסט ברור ונקי");
  if ((b.contrast||0)<-2) o.push("אתה מעדיף קונטרסט רך יותר");
  if ((b.temperature||0)>2) o.push("העריכות שלך נוטות לכיוון חם יותר");
  if ((b.temperature||0)<-2) o.push("אתה מנטרל חום ונוטה לאיזון קריר יותר");
  if ((b.clarity||0)>2) o.push("אתה מוסיף נוכחות וחדות מקומית");
  if ((b.vibrance||0)>2) o.push("אתה מאפשר לצבע לקבל יותר נוכחות");
  if ((b.exposure||0)>.1) o.push("אתה נוטה להרים מעט את החשיפה");
  if ((b.exposure||0)<-.1) o.push("אתה נוטה לשמור חשיפה מעט כהה יותר");
  const summary=o.length?`מההחלטות שלך עד עכשיו ניתן לראות ש${o.slice(0,3).join(", ו־")}.`:"עד עכשיו רוב ההצעות אושרו כמעט ללא שינוי, ולכן הסגנון שנלמד עדיין קרוב לנקודת הבסיס של המנוע.";
  return { title:dna.sample_count<8?"החתימה שלך מתחילה להופיע":"כבר רואים את שפת העריכה שלך", body:`${stated} ${summary} ${dna.sample_count<8?"זו עדיין קריאה ראשונית, ולכן ProGrapher שומר על השפעה עדינה.":"כבר יש מספיק החלטות כדי לראות חתימה עקבית יותר."}`.trim(), bullets:o.slice(0,4) };
}

function roundDisplay(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function recipeLabel(key: string) {
  const labels: Record<string, string> = {
    exposure: "חשיפה",
    highlights: "אזורים בהירים",
    shadows: "צללים",
    whites: "לבנים",
    blacks: "שחורים",
    contrast: "ניגודיות",
    temperature: "טמפרטורה",
    tint: "Tint",
    vibrance: "חיוניות",
    saturation: "רוויה",
    clarity: "בהירות מקומית",
    brightness: "Brightness",
    recovery: "Recovery",
    fill_light: "Fill Light",
  };
  return labels[key] || key;
}

function MetricCard({ label, value, suffix }: { label: string; value: number; suffix: string }) {
  return (
    <div className="panel metricCard">
      <span>{label}</span>
      <strong>{value}{suffix}</strong>
    </div>
  );
}

function RecipeCard({ label, value }: { label: string; value: number }) {
  const signed = value > 0 ? `+${value}` : `${value}`;
  return (
    <div className="recipeCard">
      <span>{label}</span>
      <strong>{signed}</strong>
    </div>
  );
}

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <div className="analysisChip">
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}
