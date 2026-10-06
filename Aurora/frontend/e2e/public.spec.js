import { expect, test } from "@playwright/test";

// Everything a visitor who is not signed in can see, plus the headers the server sends. No account, no microphone.

test("page titles say where you are", async ({ page }) => {
  for (const [path, title] of [
    ["/", "AURA — AI English Speaking Coach"],
    ["/login", "Sign in — AURA"],
    ["/signup", "Sign up — AURA"],
    ["/forgot-password", "Reset your password — AURA"],
  ]) {
    await page.goto(path);
    await expect(page).toHaveTitle(title);
  }
});

test("an address that matches nothing gets a page in the app's own look, not a bare framework error", async ({ page }) => {
  const response = await page.goto("/there-is-no-such-page");
  expect(response.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "That page isn't here" })).toBeVisible();
  await page.getByRole("link", { name: "Back to AURA" }).click();
  await expect(page).toHaveURL(/\/$/);
});

test("every page carries the security headers", async ({ request }) => {
  for (const path of ["/", "/login", "/practice"]) {
    const headers = (await request.get(path)).headers();
    expect(headers["x-content-type-options"], path).toBe("nosniff");
    expect(headers["x-frame-options"], path).toBe("DENY");
    expect(headers["content-security-policy"], path).toContain("frame-ancestors 'none'");
    expect(headers["referrer-policy"], path).toBe("strict-origin-when-cross-origin");
    expect(headers["permissions-policy"], path).toContain("microphone=(self)");
    expect(headers["x-powered-by"], path).toBeUndefined();
  }
});

test("a shared link has a preview card", async ({ request }) => {
  const html = await (await request.get("/")).text();
  expect(html).toContain('property="og:title"');
  expect(html).toContain('property="og:image"');
  expect(html).toContain('name="twitter:card"');

  const image = await request.get("/opengraph-image");
  expect(image.status()).toBe(200);
  expect(image.headers()["content-type"]).toContain("image/png");
});

test("the landing page does not promise things the app does not do", async ({ page }) => {
  await page.goto("/");
  const text = await page.locator("body").innerText();

  // The six companions differ in voice, face and name; the coach's prompt is the same for all of them.
  for (const claim of [/temperament/i, /changes? subject/i, /twice a minute/i, /follow-up questions rather than/i, /exacting about/i, /greets? you/i]) {
    expect(text, `the landing page must not say ${claim}`).not.toMatch(claim);
  }
  await expect(page.getByText("All six companions coach the same way and give the same feedback.")).toHaveCount(1);

  // The sample dashboard shows only what the real Progress screen has.
  for (const invented of [/Corrections resolved/i, /Scenarios tried/i, /Spoken this month/i]) {
    expect(text, `the sample dashboard must not show ${invented}`).not.toMatch(invented);
  }
  await expect(page.getByText("Sample data")).toBeVisible();
});

test("forgot-password: a mistyped email can be fixed, and a new code waits one minute, not fifteen", async ({ page }) => {
  await page.goto("/forgot-password");
  await page.getByPlaceholder("you@example.com").fill("typo@exmaple.com");
  await page.getByRole("button", { name: "Send code" }).click();
  await expect(page.getByRole("heading", { name: "Enter the code" })).toBeVisible();

  // The wait before asking again follows the server's one-minute cooldown, not the code's fifteen-minute life.
  const resend = page.getByRole("button", { name: /Send a new code in \d+s/ });
  await expect(resend).toBeDisabled();
  const seconds = Number((await resend.innerText()).match(/(\d+)s/)[1]);
  expect(seconds).toBeLessThanOrEqual(60);

  await page.getByRole("button", { name: "Use a different email" }).click();
  await expect(page.getByRole("heading", { name: "Forgot your password?" })).toBeVisible();
  await expect(page.getByPlaceholder("you@example.com")).toHaveValue("typo@exmaple.com"); // only the typo needs fixing
});

test("a crafted Google sign-in link cannot send the browser to another site", async ({ page }) => {
  await page.goto("/auth/google/callback?code=not-a-real-code&next=https%3A%2F%2Fevil.example%2F");
  await expect(page).toHaveURL(/\/login\?error=google_failed/);
  expect(page.url()).not.toContain("evil.example");
});
