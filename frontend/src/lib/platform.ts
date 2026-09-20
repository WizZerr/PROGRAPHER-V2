export type DesktopPlatform = "windows" | "macos" | "linux" | "unknown";

export function detectDesktopPlatform(): DesktopPlatform {
  if (typeof navigator === "undefined") {
    return "unknown";
  }

  const value = `${navigator.userAgent} ${navigator.platform}`.toLowerCase();

  if (value.includes("mac")) return "macos";
  if (value.includes("win")) return "windows";
  if (value.includes("linux")) return "linux";

  return "unknown";
}

export function primaryShortcutLabel(platform: DesktopPlatform): "Cmd" | "Ctrl" {
  return platform === "macos" ? "Cmd" : "Ctrl";
}
