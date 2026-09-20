// Compatibility bridge.
// New code should import runtime/API modules directly.
export { getEngineInfo } from "@/lib/runtime";
export { apiRequest as engineRequest } from "@/lib/api";
export { getRuntimeInfo } from "@/features/dashboard/dashboard.api";
export type { EngineInfo, RuntimeInfo } from "@/types/engine";
