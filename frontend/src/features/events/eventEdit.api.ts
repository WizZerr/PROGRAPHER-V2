import { apiRequest } from "@/lib/api";
import type { EventFolder, EventJob } from "./eventFlow";

export function listCatalogFolders(
  catalogPath: string,
): Promise<{ catalog: string; folders: EventFolder[] }> {
  return apiRequest("/api/event-edit/folders", {
    method: "POST",
    body: JSON.stringify({ catalog_path: catalogPath }),
  });
}

export function planAnchors(catalogPath: string, folderKeys: string[]): Promise<EventJob> {
  return apiRequest("/api/event-edit/plan/anchors", {
    method: "POST",
    body: JSON.stringify({ catalog_path: catalogPath, folder_keys: folderKeys }),
  });
}

export function planCompletion(catalogPath: string, folderKeys: string[]): Promise<EventJob> {
  return apiRequest("/api/event-edit/plan/complete", {
    method: "POST",
    body: JSON.stringify({ catalog_path: catalogPath, folder_keys: folderKeys }),
  });
}

export function planUndo(jobId: string): Promise<EventJob> {
  return apiRequest("/api/event-edit/plan/undo", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId }),
  });
}

export function getEventJob(jobId: string): Promise<EventJob> {
  return apiRequest(`/api/event-edit/jobs/${encodeURIComponent(jobId)}`);
}

export function confirmEventJob(jobId: string): Promise<EventJob> {
  return apiRequest(`/api/event-edit/jobs/${encodeURIComponent(jobId)}/confirm`, {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });
}

export function cancelEventJob(jobId: string): Promise<EventJob> {
  return apiRequest(`/api/event-edit/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
}
