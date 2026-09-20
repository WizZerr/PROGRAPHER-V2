import { invoke } from "@tauri-apps/api/core";
import type { EngineInfo } from "@/types/engine";

let cachedEngineInfo: EngineInfo | null = null;

export async function getEngineInfo(): Promise<EngineInfo> {
  if (cachedEngineInfo) {
    return cachedEngineInfo;
  }

  cachedEngineInfo = await invoke<EngineInfo>("get_engine_info");
  return cachedEngineInfo;
}

export function clearEngineInfoCache(): void {
  cachedEngineInfo = null;
}
