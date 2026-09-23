import { invoke } from "@tauri-apps/api/core";
import type { EngineInfo } from "@/types/engine";

let cachedEngineInfo: EngineInfo | null = null;

const ENGINE_READY_TIMEOUT_MS = 35_000;
const ENGINE_POLL_INTERVAL_MS = 120;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function readEngineInfo(): Promise<EngineInfo> {
  return invoke<EngineInfo>("get_engine_info");
}

export async function getEngineInfo(): Promise<EngineInfo> {
  if (cachedEngineInfo) {
    return cachedEngineInfo;
  }

  const startedAt = Date.now();

  while (Date.now() - startedAt < ENGINE_READY_TIMEOUT_MS) {
    const engine = await readEngineInfo();

    if (engine.status === "ready" && engine.port > 0 && engine.secret) {
      cachedEngineInfo = engine;
      return engine;
    }

    if (engine.status.startsWith("error:")) {
      throw new Error(engine.status.slice("error:".length));
    }

    await delay(ENGINE_POLL_INTERVAL_MS);
  }

  throw new Error("ProGrapher Engine did not become ready in time.");
}

export async function getEngineStartupInfo(): Promise<EngineInfo> {
  return readEngineInfo();
}

export function clearEngineInfoCache(): void {
  cachedEngineInfo = null;
}
