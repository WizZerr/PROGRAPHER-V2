import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "..");

let devServer;

if (process.platform === "win32") {
  // On Windows, spawning npm.cmd directly with shell:false can fail with
  // EINVAL on newer Node versions. Run it through cmd.exe explicitly.
  const comspec = process.env.ComSpec || "C:\\Windows\\System32\\cmd.exe";

  devServer = spawn(
    comspec,
    ["/d", "/s", "/c", "npm.cmd run dev"],
    {
      cwd: frontend,
      stdio: "inherit",
      windowsHide: true,
    },
  );
} else {
  devServer = spawn("npm", ["run", "dev"], {
    cwd: frontend,
    stdio: "inherit",
  });
}

function stopDevServer() {
  if (!devServer || devServer.killed) return;

  if (process.platform === "win32" && devServer.pid) {
    spawnSync(
      "taskkill.exe",
      ["/PID", String(devServer.pid), "/T", "/F"],
      {
        stdio: "ignore",
        windowsHide: true,
      },
    );
    return;
  }

  devServer.kill("SIGTERM");
}

process.on("SIGINT", () => {
  stopDevServer();
  process.exit(130);
});

process.on("SIGTERM", () => {
  stopDevServer();
  process.exit(143);
});

devServer.on("error", (error) => {
  console.error("Failed to start frontend dev server:", error);
  process.exit(1);
});

devServer.on("exit", (code, signal) => {
  if (signal) {
    process.exit(0);
  }

  process.exit(code ?? 0);
});
