import { apiRequest } from "@/lib/api";

export type EventSummary = {
  id: string;
  name: string;
  root_path: string;
  total_files: number;
  raw_files: number;
  rendered_files: number;
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
