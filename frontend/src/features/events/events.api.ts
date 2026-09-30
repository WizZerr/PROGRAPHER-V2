import { apiRequest } from "@/lib/api";

export type EventSummary = {
  id: string;
  name: string;
  root_path: string;
  total_files: number;
  raw_files: number;
  rendered_files: number;
  jpeg_files: number;
  created_at: string;
  updated_at: string;
};

export type EventOpenResult = "created" | "existing" | "updated";

type EventListResponse = {
  events: EventSummary[];
};

export type EventOpenResponse = {
  event: EventSummary;
  result: EventOpenResult;
  duplicate_files_ignored: number;
  new_files_added: number;
};

export type EventDeleteResponse = {
  event_id: string;
  name: string;
  removed_from_catalog: boolean;
  source_files_deleted: boolean;
};

export type EventAvailability = {
  event_id: string;
  root_exists: boolean;
  tracked_files: number;
  available_files: number;
  missing_files: number;
};

export type EventRelinkResponse = {
  event: EventSummary;
  matched_files: number;
  missing_files: number;
  new_files_added: number;
};

export type EventScanStatus =
  | "discovering"
  | "scanning"
  | "finalizing"
  | "completed"
  | "failed";

type EventScanStartResponse = {
  job_id: string;
  status: EventScanStatus;
};

export type EventScanProgress = {
  job_id: string;
  status: EventScanStatus;
  processed_files: number;
  total_files: number;
  current_file: string;
  percent: number;
  error: string | null;
  result: EventOpenResponse | null;
};

export type EventFileRecord = {
  fingerprint: string;
  filename: string;
  extension: string;
  source_type: string;
  present: boolean;
};

export async function listEventFiles(eventId: string): Promise<EventFileRecord[]> {
  const response = await apiRequest<{ files: EventFileRecord[] }>(
    `/api/events/${encodeURIComponent(eventId)}/files`,
  );
  return response.files;
}

export async function listEvents(): Promise<EventSummary[]> {
  const response = await apiRequest<EventListResponse>("/api/events");
  return response.events;
}

export async function openEventFolder(
  path: string,
): Promise<EventOpenResponse> {
  return apiRequest<EventOpenResponse>("/api/events/open-folder", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export async function startEventScan(
  path: string,
): Promise<EventScanStartResponse> {
  return apiRequest<EventScanStartResponse>("/api/events/scan", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export async function getEventScanProgress(
  jobId: string,
): Promise<EventScanProgress> {
  return apiRequest<EventScanProgress>(`/api/events/scan/${jobId}`);
}

export async function getEventAvailability(
  eventId: string,
): Promise<EventAvailability> {
  return apiRequest<EventAvailability>(
    `/api/events/${eventId}/availability`,
  );
}

export async function relinkEvent(
  eventId: string,
  path: string,
): Promise<EventRelinkResponse> {
  return apiRequest<EventRelinkResponse>(`/api/events/${eventId}/relink`, {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}


export async function deleteEvent(
  eventId: string,
): Promise<EventDeleteResponse> {
  return apiRequest<EventDeleteResponse>(
    `/api/events/${encodeURIComponent(eventId)}`,
    { method: "DELETE" },
  );
}
