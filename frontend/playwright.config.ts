import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const localPython = resolve(
  root,
  process.platform === "win32" ? "venv/Scripts/python.exe" : "venv/bin/python",
);
const python =
  process.env.PYTHON || (existsSync(localPython) ? localPython : "python");

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  workers: 2,
  use: {
    baseURL: "http://127.0.0.1:5055",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: `"${python}" -m flask --app src.web.app run --host 127.0.0.1 --port 5055`,
    cwd: root,
    url: "http://127.0.0.1:5055",
    timeout: 30000,
    stderr: "ignore",
  },
});
