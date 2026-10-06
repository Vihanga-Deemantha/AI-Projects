import { expect } from "@playwright/test";

export const API = process.env.E2E_API_BASE || "http://localhost:8000";
export const PASSWORD = "e2e-test-password-1";

/** Creates a fresh account through the sign-up form, skips email verification and lands on the practice page. */
export async function signUp(page) {
  const email = `e2e_${Date.now()}_${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/signup");
  await page.getByPlaceholder("Enter your email").fill(email);
  await page.getByPlaceholder("At least 8 characters").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();

  // A verification code was emailed; confirming it is encouraged but optional.
  await expect(page).toHaveURL(/\/verify-email/);
  await expect(page.getByRole("heading", { name: "Check your inbox" })).toBeVisible();
  await page.getByRole("link", { name: "Skip for now" }).click();
  await expect(page).toHaveURL(/\/practice/);
  return email;
}

/** Deletes the signed-in account from the profile page, as a learner would. */
export async function deleteAccount(page, email) {
  await page.goto("/profile");
  await page.getByRole("button", { name: "Delete my account" }).click();
  await page.getByPlaceholder(`Type ${email} to confirm`).fill(email);
  await page.getByPlaceholder("Your password").fill(PASSWORD);
  await page.getByRole("button", { name: "Permanently delete" }).click();
  await expect(page).toHaveURL(/localhost:\d+\/?$|\/$/);
}

/** The signed-in learner's bearer token, as the app keeps it in this browser. */
export function tokenOf(page) {
  return page.evaluate(() => localStorage.getItem("aura_token"));
}

/** Starts a session straight through the API (no microphone, no coach), for tests that need one to exist. */
export async function startSessionViaApi(request, token) {
  const res = await request.post(`${API}/api/conversation/start`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: { scenario: "casual", style: "standard", voice: "amy" },
  });
  expect(res.ok()).toBeTruthy();
  return (await res.json()).conversation_id;
}

/** One session as the server reports it in history. */
export async function sessionViaApi(request, token, conversationId) {
  const res = await request.get(`${API}/api/history/sessions/${conversationId}`, { headers: { Authorization: `Bearer ${token}` } });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

/**
 * Stands in for the server's reply to one spoken turn, so a test can exercise the microphone and the screen
 * without a real speech-to-text, language-model or voice call. `lines` are the NDJSON messages to send.
 */
export async function fakeReply(page, lines) {
  await page.route("**/api/conversation/message-stream", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/x-ndjson",
      body: lines.map((line) => JSON.stringify(line)).join("\n") + "\n",
    }),
  );
}

/** A complete, valid reply: the learner's words, the coach's answer, and "done". */
export const REPLY_OK = [
  { type: "transcript", text: "hello from the test", message_id: "m-1" },
  { type: "done", full_reply: "Nice to meet you. How was your day?", timings: { stt_ms: 120, llm_ttfs_ms: 300, first_audio_ms: 900, total_ms: 1500 } },
];
