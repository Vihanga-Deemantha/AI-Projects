/**
 * Theme persistence — light (base) / dark.
 *
 * The switch is a `data-theme` attribute on <html>, set synchronously by a
 * blocking inline script in app/layout.js (before paint, before React
 * hydrates) so there's no flash of the wrong theme. With no stored choice the
 * attribute is absent and CSS follows the OS `prefers-color-scheme`; once the
 * user picks, the attribute pins it. This module reads/writes the choice.
 */

const STORAGE_KEY = "aura_theme";

/** The theme currently in effect (explicit attribute, else the OS preference). */
export function getTheme() {
  if (typeof document === "undefined") return "light";
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "dark" || attr === "light") return attr;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function setTheme(theme) {
  if (typeof document === "undefined") return;
  const next = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    /* private mode / storage disabled — theme just won't survive a reload */
  }
}

export function toggleTheme() {
  const next = getTheme() === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}

/**
 * Source for the blocking inline script in app/layout.js. Kept here so the
 * storage key stays in one place — but this exact string is inlined at
 * build time via <script dangerouslySetInnerHTML>, not imported at runtime
 * (it has to run before any module import resolves).
 */
export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("${STORAGE_KEY}");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t);}catch(e){}})();`;
