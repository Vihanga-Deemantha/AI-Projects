import { expect, test } from "@playwright/test";
import { deleteAccount, signUp } from "./helpers.js";

// Runs in the "phone" project (see playwright.config.mjs): a 390 x 844 touch screen.

/** How many pixels wider than the screen the page is (0 means it does not scroll sideways). */
async function sidewaysOverflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
}

test("pages that need no account do not scroll sideways on a phone", async ({ page }) => {
  for (const path of ["/", "/login", "/signup", "/forgot-password"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    expect(await sidewaysOverflow(page), `${path} scrolls sideways`).toBeLessThanOrEqual(1);
  }
});

test("on a phone the menu is a drawer that keeps the keyboard inside it, and no page scrolls sideways", async ({ page }) => {
  const email = await signUp(page);
  const drawer = page.locator("#app-sidebar");
  const openButton = page.locator('button[aria-label="Open menu"]');

  // Closed: its links are slid off-screen, so they must not be reachable with Tab either.
  await expect(drawer).toHaveAttribute("inert", "");
  await expect(openButton).toHaveAttribute("aria-expanded", "false");

  await openButton.click();
  await expect(drawer).not.toHaveAttribute("inert", "");
  await expect(page.getByRole("button", { name: "Close menu" })).toBeFocused();
  await expect(page.locator("div.contents[inert]")).toHaveCount(1); // the page behind the open drawer cannot be reached

  // Escape closes it and hands focus back to the button that opened it.
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveAttribute("inert", "");
  await expect(openButton).toBeFocused();

  // A link in the drawer closes it as the page changes.
  await openButton.click();
  await drawer.getByRole("link", { name: "History" }).click();
  await expect(page).toHaveURL(/\/history$/);
  await expect(drawer).toHaveAttribute("inert", "");

  for (const path of ["/practice", "/progress", "/history", "/profile"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    expect(await sidewaysOverflow(page), `${path} scrolls sideways`).toBeLessThanOrEqual(1);
  }

  await deleteAccount(page, email);
});
