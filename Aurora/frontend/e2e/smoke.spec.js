import { expect, test } from "@playwright/test";

const API = process.env.E2E_API_BASE || "http://localhost:8000";
const PASSWORD = "e2e-test-password-1";

/** Creates a fresh account through the sign-up form, skips email verification and lands on the practice page. */
async function signUp(page) {
  const email = `e2e_${Date.now()}@example.com`;
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
async function deleteAccount(page, email) {
  await page.goto("/profile");
  await page.getByRole("button", { name: "Delete my account" }).click();
  await page.getByPlaceholder(`Type ${email} to confirm`).fill(email);
  await page.getByPlaceholder("Your password").fill(PASSWORD);
  await page.getByRole("button", { name: "Permanently delete" }).click();
  await expect(page).toHaveURL(/localhost:\d+\/?$|\/$/);
}

/**
 * One journey through everything a learner does: sign up, hold the mic and
 * speak, see the coach reply and the corrections arrive, end the session, find
 * it in history, then delete the account.
 */
test("a learner can sign up, practise, review their history and delete their account", async ({ page, request }) => {
  // ── Sign up ────────────────────────────────────────────────────────────────
  const email = await signUp(page);

  // Route guards: the unverified-email nudge is shown in the sidebar.
  await expect(page.getByText("Verify your email").first()).toBeVisible();

  // A new learner starts at the default difficulty, with a note that it adapts.
  await expect(page.getByText("Elementary", { exact: true })).toBeVisible();
  await expect(page.getByText(/Starting at a comfortable level/)).toBeVisible();

  // ── Speak: hold the mic for the whole fixture sentence (~7 s), then release ─
  const mic = page.getByRole("button", { name: "Hold to talk" });
  const box = await mic.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await expect(page.getByRole("button", { name: /Recording/ })).toBeVisible();
  await page.waitForTimeout(8_000);
  await page.mouse.up();

  // Transcript of what was said, then the coach's spoken reply as a bubble.
  await expect(page.getByText(/to the mall/i).first()).toBeVisible();
  await expect(page.locator("main").getByText("This session has no turns")).toHaveCount(0);
  await expect(page.getByLabel(/is thinking/)).toHaveCount(0, { timeout: 60_000 });

  // How they spoke: fluency chips under their bubble, and the session tile.
  await expect(page.getByText(/^Fluency \d+$/).first()).toBeVisible();
  await expect(page.getByText(/^\d+ wpm$/).first()).toBeVisible();
  await expect(page.getByText(/^\d+ pauses?$/).first()).toBeVisible();
  await expect(page.getByText(/^Clarity \d+\*?$/).first()).toBeVisible();

  // Corrections arrive on their own — the session has NOT been ended.
  await expect(page.getByText(/^[1-9]\d* this session$/i)).toBeVisible();
  await expect(page.getByText(/past tense|past_tense|tense|agreement/i).first()).toBeVisible();

  // ── End the session ────────────────────────────────────────────────────────
  await page.getByRole("button", { name: "End session" }).click();
  await expect(page.getByText("Session complete.")).toBeVisible();

  // ── The report (it can take a few seconds while the last answer is analysed) ─
  await page.getByRole("link", { name: /See your report/ }).click();
  await expect(page.getByRole("heading", { name: "How that went" })).toBeVisible();
  await expect(page.getByText(/Elementary level/)).toBeVisible(); // the level the session ran at
  await expect(page.getByRole("img", { name: /Overall score \d+ out of 100/ })).toBeVisible({ timeout: 60_000 });
  for (const dimension of ["Grammar", "Vocabulary", "Fluency", "Clarity", "Naturalness"]) {
    await expect(page.getByRole("progressbar", { name: dimension })).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: "What went well" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Work on next" })).toBeVisible();

  // ── History ────────────────────────────────────────────────────────────────
  await page.goto("/history");
  await expect(page.getByText("Casual chat · Standard")).toBeVisible();
  await expect(page.getByText(/with .* · Elementary level/)).toBeVisible();
  await page.getByText("Casual chat · Standard").click();
  await expect(page.getByText("Transcript")).toBeVisible();
  await expect(page.getByText(/to the mall/i).first()).toBeVisible();

  // ── Difficulty: pin a level on the profile, and the practice page reflects it ─
  await page.goto("/profile#difficulty");
  await page.getByRole("button", { name: "Advanced", exact: true }).click();
  await expect(page.getByText("You chose this level.")).toBeVisible();
  await page.goto("/practice");
  await expect(page.getByText("Advanced", { exact: true })).toBeVisible();

  // ── Delete the account ─────────────────────────────────────────────────────
  await deleteAccount(page, email);

  const login = await request.post(`${API}/api/auth/login`, { data: { email, password: PASSWORD } });
  expect(login.status()).toBe(401);
});

/**
 * A speaking style sets the coach's words AND the accent heard, and not every companion has a voice for
 * every accent (Australian exists only for Ryan and Alan), so the pickers only offer pairs that work and
 * say why the rest are off. No microphone and no coach reply: setup only, so it runs in seconds.
 */
test("a speaking style brings its accent, and only companions who can speak it are on offer", async ({ page }) => {
  const email = await signUp(page);
  const australian = page.getByRole("button", { name: "Australian English", exact: true });
  const noAustralianVoice = (name) => page.getByTitle(`${name} doesn't have an Australian voice yet. Ryan and Alan do.`);

  // Standard English is the companion's own voice, and nobody is switched off.
  await expect(page.getByTitle(/^Amy · American accent by default\. It changes with your speaking style\./)).toBeEnabled();
  await expect(page.getByText("Amy's own voice (American accent).")).toBeVisible();

  // Amy has no Australian voice, so that style is off for her, and the hover says who does have one.
  await expect(australian).toBeDisabled();
  await expect(australian).toHaveAttribute("title", "Amy doesn't have an Australian voice yet. Ryan and Alan do.");

  // Pick Ryan and Australian opens up; the note says what will be heard.
  await page.getByTitle(/^Ryan · /).click();
  await expect(australian).toBeEnabled();
  const saved = page.waitForResponse((r) => r.url().endsWith("/api/auth/profile") && r.request().method() === "PATCH" && r.request().postData()?.includes("australian"));
  await australian.click();
  await expect(page.getByText("Ryan will speak with an Australian accent.")).toBeVisible();

  // The companions without an Australian voice are now switched off, each with the reason on hover.
  for (const name of ["Eida", "Maya", "Amy", "Lessac"]) await expect(noAustralianVoice(name)).toBeDisabled();
  await expect(page.getByTitle(/^Alan · will speak with an Australian accent, to match your speaking style\./)).toBeEnabled();

  // The pair is saved to the profile, which shows the same companions switched off.
  expect((await saved).ok()).toBe(true);
  await page.goto("/profile");
  await expect(page.getByRole("button", { name: "Australian English", exact: true })).toHaveAttribute("aria-pressed", "true");
  for (const name of ["Eida", "Maya", "Amy", "Lessac"]) await expect(noAustralianVoice(name)).toBeDisabled();

  // The practice page opens on that pair, and starting a session sends it to a server that accepts it.
  await page.goto("/practice");
  await expect(page.getByText("Ryan will speak with an Australian accent.")).toBeVisible();
  const started = page.waitForResponse((r) => r.url().endsWith("/api/conversation/start"));
  await page.getByRole("button", { name: "Start session" }).click();
  const session = await (await started).json();
  expect(session).toMatchObject({ voice: "ryan", style: "australian" });
  await expect(page.getByRole("button", { name: "End session" })).toBeVisible();

  await deleteAccount(page, email);
});

/**
 * A companion and style saved before styles brought an accent can be a pair nobody can speak (say Amy
 * with Australian). The profile says so and offers the way out, and the practice page starts from
 * Standard English rather than from a pair the server would refuse.
 */
test("a saved pair with no voice behind it is explained, and sessions start in Standard English", async ({ page }) => {
  const email = await signUp(page);

  // Pretend the server remembers Amy with Australian, as an account from before this change might.
  const legacy = { preferred_voice: "amy", preferred_style: "australian" };
  await page.route("**/api/auth/me", async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...(await response.json()), ...legacy } });
  });
  await page.evaluate((legacy) => {
    const user = JSON.parse(localStorage.getItem("aura_user"));
    localStorage.setItem("aura_user", JSON.stringify({ ...user, ...legacy }));
  }, legacy);

  await page.goto("/profile");
  await expect(page.getByText("Amy doesn't have an Australian voice yet, so your sessions will start in Standard English")).toBeVisible();
  await expect(page.getByRole("button", { name: "Standard English", exact: true })).toBeEnabled(); // the way out

  await page.goto("/practice");
  await expect(page.getByRole("button", { name: "Standard English", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Amy's own voice (American accent).")).toBeVisible();

  await page.unroute("**/api/auth/me");
  await deleteAccount(page, email);
});

test("protected pages send a signed-out visitor to the login screen", async ({ page }) => {
  for (const path of ["/practice", "/history", "/profile", "/verify-email"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/login/);
  }
});
