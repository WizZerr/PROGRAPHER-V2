import { invoke } from "@tauri-apps/api/core";

export type EngineInfo = {
  host: string;
  port: number;
  secret: string;
  status: string;
};

export type RuntimeInfo = {
  status: string;
  service: string;
  version: string;
};

let cachedEngineInfo: EngineInfo | null = null;

export async function getEngineInfo(): Promise<EngineInfo> {
  if (cachedEngineInfo) {
    return cachedEngineInfo;
  }

  cachedEngineInfo = await invoke<EngineInfo>("get_engine_info");
  return cachedEngineInfo;
}

export async function engineRequest<T>(
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

export async function getRuntimeInfo(): Promise<RuntimeInfo> {
  return engineRequest<RuntimeInfo>("/api/runtime");
}
