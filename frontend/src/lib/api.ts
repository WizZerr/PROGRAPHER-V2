import { getEngineInfo } from "@/lib/runtime";

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const engine = await getEngineInfo();

  const headers = new Headers(init.headers);
  headers.set("X-ProGrapher-Secret", engine.secret);

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(
    `http://${engine.host}:${engine.port}${path}`,
    {
      ...init,
      headers,
    },
  );

  if (!response.ok) {
    let detail = `Engine request failed: ${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail.trim()) {
        detail = body.detail;
      }
    } catch {
      // The engine did not return a JSON error body.
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export async function apiBlobRequest(
  path: string,
  init: RequestInit = {},
): Promise<Blob> {
  const engine = await getEngineInfo();
  const headers = new Headers(init.headers);
  headers.set("X-ProGrapher-Secret", engine.secret);

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(
    `http://${engine.host}:${engine.port}${path}`,
    {
      ...init,
      headers,
    },
  );

  if (!response.ok) {
    let detail = `Engine request failed: ${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail.trim()) {
        detail = body.detail;
      }
    } catch {
      // The engine did not return a JSON error body.
    }
    throw new Error(detail);
  }

  return response.blob();
}

export async function apiBlob(path: string): Promise<Blob> {
  try {
    return await apiBlobRequest(path);
  } catch {
    throw new Error("אין תצוגת מצלמה לקובץ הזה.");
  }
}
