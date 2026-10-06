import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));

/**
 * End-to-end smoke test (npm run e2e).
 *
 * It drives the REAL app, so the whole stack must already be running:
 *   docker compose up -d
 *   uvicorn backend.main:app          (from Aurora/, with your .env — it makes one real
 *                                      Groq call and runs Whisper + Piper)
 *   npm run dev                       (from Aurora/frontend)
 *
 * The microphone is Chrome's built-in fake device playing e2e/fixtures/speech.wav
 * (a Piper-generated sentence with deliberate grammar mistakes), so the real
 * getUserMedia -> MediaRecorder -> upload path is exercised without hardware.
 *
 * Uses your installed Google Chrome (channel "chrome"), so no browser download is
 * needed. Point at another deployment with E2E_BASE_URL / E2E_API_BASE.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 150_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    channel: "chrome",
    permissions: ["microphone"],
    launchOptions: {
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        `--use-file-for-fake-audio-capture=${path.join(here, "e2e", "fixtures", "speech.wav")}`,
      ],
    },
    trace: "retain-on-failure",
  },
});
