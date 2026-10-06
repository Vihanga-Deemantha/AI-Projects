import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));

/**
 * End-to-end tests (npm run e2e).
 *
 * They drive the REAL app, so the whole stack must already be running:
 *   docker compose up -d
 *   uvicorn backend.main:app          (from Aurora/, with your .env — the journey in smoke.spec.js
 *                                      makes real Groq calls and runs Whisper + Piper)
 *   npm run dev                       (from Aurora/frontend)
 *
 * The microphone is Chrome's built-in fake device playing e2e/fixtures/speech.wav
 * (a Piper-generated sentence with deliberate grammar mistakes), so the real
 * getUserMedia -> MediaRecorder -> upload path is exercised without hardware.
 * Specs that only need the screen to react to a turn fake the server's reply (helpers.js fakeReply), so they
 * spend no speech-to-text or language-model calls.
 *
 *   smoke.spec.js          the whole journey, plus the accent pickers and route guards
 *   lifecycle.spec.js      leaving mid-session, finishing a session later, replies that are cut off
 *   accessibility.spec.js  keyboard use of the microphone, tap-to-talk, titles, and an axe scan of every page
 *   public.spec.js         what a signed-out visitor sees, the security headers, the preview card
 *   responsive.spec.js     the "phone" project: the drawer menu and no sideways scrolling at 390 px
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
  projects: [
    { name: "desktop", testIgnore: /responsive\.spec\.js/ },
    {
      name: "phone",
      testMatch: /responsive\.spec\.js/,
      use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
  ],
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
