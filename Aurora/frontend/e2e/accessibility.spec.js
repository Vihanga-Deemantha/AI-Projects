import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { deleteAccount, fakeReply, REPLY_OK, signUp } from "./helpers.js";

/**
 * Fails on any accessibility problem of moderate, serious or critical impact (WCAG 2.0/2.1 A and AA, plus axe's
 * best-practice rules such as "one main landmark" and "heading levels go up by one"), naming each one.
 * Colour contrast is not decided by axe on this app's layered, animated backgrounds, so the palette is
 * checked by calculation instead (see the contrast notes in app/globals.css).
 */
async function expectNoProblems(page, where) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"])
    .analyze();
  const found = violations
    .filter((v) => ["moderate", "serious", "critical"].includes(v.impact))
    .map((v) => `${v.id} (${v.impact}): ${v.help}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
  expect(found, `${where} has accessibility problems`).toEqual([]);
}

test.describe("keyboard", () => {
  test("the microphone works by holding Space, or Enter, on the focused button", async ({ page }) => {
    const email = await signUp(page);

    for (const key of ["Space", "Enter"]) {
      await fakeReply(page, [
        { type: "transcript", text: `spoken with ${key}`, message_id: `m-${key}` },
        { type: "done", full_reply: `Heard you using ${key}.`, timings: {} },
      ]);
      await page.getByRole("button", { name: "Hold to talk" }).focus();
      await page.keyboard.down(key);
      await expect(page.getByRole("button", { name: /Recording/ })).toBeVisible();
      await page.waitForTimeout(1_200);
      await page.keyboard.up(key);
      await expect(page.getByText(`Heard you using ${key}.`)).toBeVisible();
    }

    await deleteAccount(page, email);
  });

  test("tap-to-talk: one tap starts, the next sends, and the choice is remembered", async ({ page }) => {
    const email = await signUp(page);
    await fakeReply(page, REPLY_OK);

    await page.getByRole("button", { name: "Switch to tap-to-talk" }).click();
    await page.getByRole("button", { name: "Tap to talk" }).click();
    const recording = page.getByRole("button", { name: "Recording — tap to send" });
    await expect(recording).toBeVisible();
    await page.waitForTimeout(1_200);
    await recording.click();
    await expect(page.getByText("Nice to meet you. How was your day?")).toBeVisible();

    await page.reload();
    await expect(page.getByRole("button", { name: "Tap to talk" })).toBeVisible(); // remembered in this browser
    await page.getByRole("button", { name: "Switch to hold-to-talk" }).click();
    await expect(page.getByRole("button", { name: "Hold to talk" })).toBeVisible();

    await deleteAccount(page, email);
  });

  test("a switched-off choice explains itself in words, and can still be reached with the keyboard", async ({ page }) => {
    const email = await signUp(page);
    const australian = page.getByRole("button", { name: "Australian English", exact: true });

    // Written on the page, not only in a tooltip that a phone never shows.
    await expect(page.getByText("Amy doesn't have an Australian voice yet. Ryan and Alan do.")).toBeVisible();
    await expect(australian).toHaveAttribute("aria-disabled", "true");
    await expect(australian).toHaveAttribute("aria-describedby", "style-note");

    // aria-disabled, not disabled: Tab can land on it, so a screen reader can read why it is off.
    await australian.focus();
    await expect(australian).toBeFocused();
    await australian.press("Enter"); // and pressing it does nothing
    await expect(page.getByRole("button", { name: "Standard English", exact: true })).toHaveAttribute("aria-pressed", "true");

    // Pick a companion who has the voice, then that style: now it is the companions who are switched off, and the
    // sentence under their row says who does have it.
    await page.getByTitle(/^Ryan · /).click();
    await expect(page.getByText("Only Ryan and Alan have an Australian voice yet.")).toHaveCount(0); // under Standard English nobody is off
    await page.getByRole("button", { name: "Australian English", exact: true }).click();
    await expect(page.getByText("Only Ryan and Alan have an Australian voice yet.")).toBeVisible();

    await deleteAccount(page, email);
  });

  test("the sidebar marks the current page, and page titles say where you are", async ({ page }) => {
    const email = await signUp(page);
    const nav = page.getByRole("navigation", { name: "Main" });

    for (const [path, link, title] of [
      ["/practice", "Practice", "Practice — AURA"],
      ["/progress", "Progress", "Progress — AURA"],
      ["/history", "History", "History — AURA"],
      ["/profile", "Profile", "Profile — AURA"],
    ]) {
      await nav.getByRole("link", { name: link }).click();
      await expect(page).toHaveURL(new RegExp(`${path}$`));
      await expect(nav.getByRole("link", { name: link })).toHaveAttribute("aria-current", "page");
      await expect(page).toHaveTitle(title);
    }

    await deleteAccount(page, email);
  });
});

test.describe("automated accessibility scan (axe)", () => {
  for (const [path, name] of [["/", "the landing page"], ["/login", "the sign-in page"], ["/signup", "the sign-up page"], ["/forgot-password", "the reset-password page"]]) {
    test(`${name} has no accessibility problems`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expectNoProblems(page, name);
    });
  }

  test("the signed-in pages have no accessibility problems", async ({ page }) => {
    const email = await signUp(page);
    for (const [path, name] of [["/practice", "practice"], ["/progress", "progress"], ["/history", "history"], ["/profile", "profile"]]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expectNoProblems(page, name);
    }
    await deleteAccount(page, email);
  });
});
