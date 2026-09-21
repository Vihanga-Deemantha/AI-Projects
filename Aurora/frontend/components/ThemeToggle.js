"use client";

import { useEffect, useState } from "react";
import { getTheme, toggleTheme } from "@/lib/theme";

/** Text button that flips between the light and dark palettes; the label names the theme it switches TO. */
export default function ThemeToggle({ className = "" }) {
  const [theme, setThemeState] = useState("light");

  // Read after mount: the real theme was already applied pre-paint by the
  // blocking script in layout.js — this just syncs the label.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing from the DOM attribute / OS preference the init script already resolved, not deriving from props/state
    setThemeState(getTheme());
  }, []);

  return (
    <button
      type="button"
      onClick={() => setThemeState(toggleTheme())}
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      className={`h-9 shrink-0 cursor-pointer border border-panel-border px-3.5 text-[10px] font-bold tracking-[0.18em] whitespace-nowrap text-soft uppercase transition hover:border-brand hover:text-brand ${className}`}
    >
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}
