"use client";

import { useEffect, useState } from "react";
import { getTheme, toggleTheme } from "@/lib/theme";

/** Sun/moon icon button — switches between AURA Midnight and AURA Clarity. */
export default function ThemeToggle({ className = "" }) {
  const [theme, setThemeState] = useState("dark");

  // Read after mount: the real theme was already applied pre-paint by the
  // blocking script in layout.js — this just syncs this component's icon.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing from the DOM attribute the blocking init script already set, not deriving from props/state
    setThemeState(getTheme());
  }, []);

  return (
    <button
      type="button"
      onClick={() => setThemeState(toggleTheme())}
      aria-label={theme === "light" ? "Switch to AURA Midnight (dark)" : "Switch to AURA Clarity (light)"}
      title={theme === "light" ? "Switch to Midnight" : "Switch to Clarity"}
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-panel-border text-foreground/60 transition hover:border-brand/40 hover:text-brand ${className}`}
    >
      {theme === "light" ? <MoonIcon className="h-4 w-4" /> : <SunIcon className="h-4 w-4" />}
    </button>
  );
}

function SunIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" strokeLinecap="round" />
    </svg>
  );
}

function MoonIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
