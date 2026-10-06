import { expect, test } from "@playwright/test";
import { deleteAccount, fakeReply, sessionViaApi, signUp, startSessionViaApi, tokenOf } from "./helpers.js";

/** Holds the mic (the browser's fake microphone) for `ms`, then lets go, like a learner speaking. */
async function speak(page, ms = 1_200) {
  const mic = page.getByRole("button", { name: "Hold to talk" });
  const box = await mic.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await expect(page.getByRole("button", { name: /Recording/ })).toBeVisible();
  await page.waitForTimeout(ms);
  await page.mouse.up();
}

test("leaving the practice page ends the session and leaves no audio running", async ({ page, request }) => {
  // Remember every audio context the page makes, to prove that none is left open once the learner has gone.
  await page.addInitScript(() => {
    window.__contexts = [];
    const Original = window.AudioContext;
    window.AudioContext = class extends Original {
      constructor(...args) {
        super(...args);
        window.__contexts.push(this);
      }
    };
  });

  const email = await signUp(page);
  const token = await tokenOf(page);

  const started = page.waitForResponse((r) => r.url().endsWith("/api/conversation/start"));
  await page.getByRole("button", { name: "Start session" }).click();
  const { conversation_id: id } = await (await started).json();
  await expect(page.getByRole("button", { name: "End session" })).toBeVisible();
  expect((await sessionViaApi(request, token, id)).is_complete).toBe(false);

  // Walk away without pressing "End session": a link inside the app.
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "History" }).click();
  await expect(page).toHaveURL(/\/history$/);

  await expect.poll(async () => (await sessionViaApi(request, token, id)).is_complete, { timeout: 15_000 }).toBe(true);

  const states = await page.evaluate(() => window.__contexts.map((c) => c.state));
  expect(states.length).toBeGreaterThan(0);
  expect(states, "every audio context the practice page made must be closed").toEqual(states.map(() => "closed"));

  await deleteAccount(page, email);
});

test("navigating away from the site, not only clicking a link inside it, also ends the session", async ({ page, request }) => {
  const email = await signUp(page);
  const token = await tokenOf(page);

  const started = page.waitForResponse((r) => r.url().endsWith("/api/conversation/start"));
  await page.getByRole("button", { name: "Start session" }).click();
  const { conversation_id: id } = await (await started).json();
  await expect(page.getByRole("button", { name: "End session" })).toBeVisible();

  await page.goto("about:blank"); // out of the site: the browser fires "pagehide"
  await expect.poll(async () => (await sessionViaApi(request, token, id)).is_complete, { timeout: 15_000 }).toBe(true);

  // The Back button may bring the page back from the browser's cache looking exactly as it was left. Either way it
  // must not offer to end a session that is already over.
  await page.goBack();
  await expect(page.getByRole("button", { name: /Start (new )?session/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "End session" })).toHaveCount(0);

  await deleteAccount(page, email);
});

test("a session that was left open can be finished later from its History page", async ({ page, request }) => {
  const email = await signUp(page);
  const token = await tokenOf(page);
  const id = await startSessionViaApi(request, token); // left open, as if the tab had been closed

  await page.goto(`/history/${id}`);
  await expect(page.getByText("This session was never finished.")).toBeVisible();
  await page.getByRole("button", { name: "Finish session" }).click();
  await expect(page.getByText("This session was never finished.")).toHaveCount(0);

  const session = await sessionViaApi(request, token, id);
  expect(session.is_complete).toBe(true);
  expect(session.turn_count).toBe(0);

  await deleteAccount(page, email);
});

test("a reply that is cut off part-way is reported, and its half-finished bubble does not stay faded", async ({ page }) => {
  const email = await signUp(page);
  // The connection drops after the first sentence: there is no "done".
  await fakeReply(page, [
    { type: "transcript", text: "this reply will be cut off", message_id: "m-1" },
    { type: "audio_chunk", index: 0, text: "Here is the start of my answer", data: "", tts_ms: 1 },
  ]);

  await speak(page);

  // (Next has its own role="alert" element outside <main>, to announce page changes.)
  await expect(page.locator("main").getByRole("alert")).toContainText("The connection dropped before the reply finished");
  await expect(page.getByText("Here is the start of my answer")).toBeVisible();
  await expect(page.locator("main .opacity-70"), "a finished-or-failed reply must not look like it is still arriving").toHaveCount(0);

  // And the learner can simply try again.
  await fakeReply(page, [
    { type: "transcript", text: "second try", message_id: "m-2" },
    { type: "done", full_reply: "That worked.", timings: {} },
  ]);
  await speak(page);
  await expect(page.getByText("That worked.")).toBeVisible();

  await deleteAccount(page, email);
});

test("the coach stops talking when the session is ended, even if more of the reply is still arriving", async ({ page }) => {
  await page.addInitScript(() => {
    window.__contexts = [];
    const Original = window.AudioContext;
    window.AudioContext = class extends Original {
      constructor(...args) {
        super(...args);
        window.__contexts.push(this);
      }
    };
  });
  const email = await signUp(page);

  await page.getByRole("button", { name: "Start session" }).click();
  await expect(page.getByRole("button", { name: "End session" })).toBeVisible();
  await page.getByRole("button", { name: "End session" }).click();
  await expect(page.getByText("Session complete.")).toBeVisible();

  const open = await page.evaluate(() => window.__contexts.filter((c) => c.state !== "closed").length);
  expect(open, "no audio context may stay open after the session has ended").toBe(0);

  await deleteAccount(page, email);
});
