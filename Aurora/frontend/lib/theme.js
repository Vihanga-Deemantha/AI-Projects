/**
 * Theme persistence — AURA Midnight (dark, default) / AURA Clarity (light).
 *
 * The actual switch is a `data-theme` attribute on <html>, set synchronously
 * by a blocking inline script in app/layout.js (before paint, before React
 * hydrates) so there's no flash of the wrong theme on load. This module is
 * for reading/writing the stored choice afterward, from ThemeToggle.
 */

const STORAGE_KEY = "aura_theme";

export function getTheme() {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

export function setTheme(theme) {
  if (typeof document === "undefined") return;
  if (theme === "light") {
    document.documentElement.setAttribute("data-theme", "light");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* private mode / storage disabled — theme just won't survive a reload */
  }
}

export function toggleTheme() {
  const next = getTheme() === "light" ? "dark" : "light";
  setTheme(next);
  return next;
}

/**
 * Source for the blocking inline script in app/layout.js. Kept here so the
 * storage key stays in one place — but this exact string is inlined at
 * build time via <script dangerouslySetInnerHTML>, not imported at runtime
 * (it has to run before any module import resolves).
 */
export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("${STORAGE_KEY}");if(t==="light")document.documentElement.setAttribute("data-theme","light");}catch(e){}})();`;
