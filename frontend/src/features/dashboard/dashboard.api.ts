import { apiRequest } from "@/lib/api";
import type { RuntimeInfo } from "@/types/engine";

export function getRuntimeInfo(): Promise<RuntimeInfo> {
  return apiRequest<RuntimeInfo>("/api/runtime");
}
