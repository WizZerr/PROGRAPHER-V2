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
    throw new Error(
      `Engine request failed: ${response.status} ${response.statusText}`,
    );
  }

  return (await response.json()) as T;
}
