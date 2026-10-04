import { apiBlobRequest } from "@/lib/api";

export type JpegGlobalControls = {
  brightness: number;
  contrast: number;
  warmth: number;
  tint: number;
};

export const JPEG_NEUTRAL_CONTROLS: JpegGlobalControls = {
  brightness: 0,
  contrast: 0,
  warmth: 0,
  tint: 0,
};

export async function renderJpegControlPreview(input: {
  eventId: string;
  fingerprint: string;
  revision: number;
  controls: JpegGlobalControls;
}): Promise<Blob> {
  return apiBlobRequest("/api/jpeg-controls/preview", {
    method: "POST",
    body: JSON.stringify({
      event_id: input.eventId,
      fingerprint: input.fingerprint,
      revision: input.revision,
      controls: input.controls,
    }),
  });
}
