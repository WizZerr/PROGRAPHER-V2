import { spawn, spawnSync } from "node:child_process";
import { existsSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "..");
const project = path.resolve(frontend, "..");
const backend = path.join(project, "backend");
const binaries = path.join(frontend, "src-tauri", "binaries");

const python =
  process.platform === "win32"
    ? path.join(backend, ".venv", "Scripts", "python.exe")
    : path.join(backend, ".venv", "bin", "python");

const prepare = path.join(
  backend,
  "packaging",
  "prepare_tauri_sidecar.py",
);

function newestMtime(target) {
  if (!existsSync(target)) return 0;

  const stat = statSync(target);
  if (stat.isFile()) return stat.mtimeMs;

  let newest = 0;

  for (const entry of readdirSync(target, { withFileTypes: true })) {
    if ([".venv", "build", "dist", "__pycache__"].includes(entry.name)) {
      continue;
    }

    newest = Math.max(
      newest,
      newestMtime(path.join(target, entry.name)),
    );
  }

  return newest;
}

function newestSidecarMtime() {
  if (!existsSync(binaries)) return 0;

  let newest = 0;

  for (const entry of readdirSync(binaries, { withFileTypes: true })) {
    if (
      entry.isFile() &&
      entry.name.startsWith("prographer-engine-")
    ) {
      newest = Math.max(
        newest,
        statSync(path.join(binaries, entry.name)).mtimeMs,
      );
    }
  }

  return newest;
}

const backendMtime = Math.max(
  newestMtime(path.join(backend, "app")),
  newestMtime(path.join(backend, "desktop_entry.py")),
  newestMtime(path.join(backend, "requirements-lock.txt")),
  newestMtime(prepare),
);

const sidecarMtime = newestSidecarMtime();

if (backendMtime > sidecarMtime) {
  if (!existsSync(python)) {
    console.error(
      `ProGrapher backend venv Python not found: ${python}`,
    );
    process.exit(1);
  }

  console.log(
    "Backend changed — rebuilding ProGrapher sidecar...",
  );

  const build = spawnSync(python, [prepare], {
    cwd: backend,
    stdio: "inherit",
  });

  if (build.status !== 0) {
    process.exit(build.status ?? 1);
  }
} else {
  console.log("ProGrapher sidecar is current.");
}

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
