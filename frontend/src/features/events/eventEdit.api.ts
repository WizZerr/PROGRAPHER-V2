import { apiRequest } from "@/lib/api";

export type AnchorPlan = {
  photos: number;
  moments: number;
  anchors: number;
  photos_in_anchored_moments: number;
  collection: string;
  label: string;
  labelled: number;
  backup: string | null;
};

export type AutomaticExposure = {
  state: "on" | "off";
  reason:
    | "disabled"
    | "face_model_missing"
    | "no_smart_previews"
    | "decoder_unavailable"
    | "too_few_anchor_faces"
    | null;
  photos?: number;
};

export type CompleteResult = {
  photos: number;
  moments: number;
  anchors: number;
  anchors_edited: number;
  from_anchor: number;
  automatic: number;
  event_level: number;
  skipped_edited: number;
  no_exposure: number;
  automatic_exposure: AutomaticExposure;
  written: number;
  skipped: Record<string, number>;
  backup: string | null;
  seconds: number;
};

export function chooseAnchors(catalogPath: string): Promise<AnchorPlan> {
  return apiRequest<AnchorPlan>("/api/event-edit/anchors", {
    method: "POST",
    body: JSON.stringify({ catalog_path: catalogPath }),
  });
}

export function completeEvent(catalogPath: string): Promise<CompleteResult> {
  return apiRequest<CompleteResult>("/api/event-edit/complete", {
    method: "POST",
    body: JSON.stringify({ catalog_path: catalogPath, automatic_exposure: true }),
  });
}

export function undoEventStep(
  catalogPath: string,
  backup: string,
): Promise<{ restored: boolean }> {
  return apiRequest<{ restored: boolean }>("/api/event-edit/undo", {
    method: "POST",
    body: JSON.stringify({ catalog_path: catalogPath, backup }),
  });
}
