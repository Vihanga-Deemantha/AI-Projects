"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getStoredUser, logout } from "@/lib/auth";
import ThemeToggle from "@/components/ThemeToggle";

/** Persistent left navigation for every authenticated screen (Practice / History). */
export default function AppSidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState(null);

  // Read after mount: localStorage isn't available during SSR, and reading it
  // during render would mismatch the server-rendered output on hydration.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is client-only; reading it during render would mismatch SSR output
    setUser(getStoredUser());
  }, []);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  const label = user?.display_name || user?.email || "Account";
  const initial = (user?.display_name || user?.email || "A").charAt(0).toUpperCase();

  return (
    <aside className="flex w-56 shrink-0 flex-col gap-1.5 border-r border-panel-border bg-surface px-4 py-7">
      <Link href="/" className="mb-6 flex items-center gap-2.5 px-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-linear-to-br from-brand to-brand-dark font-display text-sm font-bold text-white shadow-[0_0_16px_rgba(139,124,255,0.5)]">
          A
        </span>
        <span className="font-display text-lg font-bold">AURA</span>
      </Link>

      <NavItem href="/practice" active={pathname === "/practice"} icon={<CompassIcon />}>
        Practice
      </NavItem>
      <NavItem href="/history" active={pathname.startsWith("/history")} icon={<HistoryIcon />}>
        History
      </NavItem>
      <NavItem icon={<ChartIcon />} disabled note="Soon">
        Progress
      </NavItem>

      <div className="mt-auto flex flex-col gap-3 border-t border-panel-border pt-4">
        <ThemeToggle />
        <div className="flex items-center gap-2.5 px-1">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-linear-to-br from-sky-300 to-brand text-xs font-bold text-white">
            {initial}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold">{label}</p>
            <button
              type="button"
              onClick={handleLogout}
              className="text-[11px] text-foreground/40 transition hover:text-brand"
            >
              Log out
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}

function NavItem({ href, active, disabled, note, icon, children }) {
  const classes = `flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-medium transition ${
    active
      ? "bg-brand-soft text-foreground"
      : disabled
        ? "cursor-not-allowed text-foreground/30"
        : "text-foreground/60 hover:text-foreground"
  }`;

  const content = (
    <>
      <span className={`h-[18px] w-[18px] ${active ? "text-brand" : ""}`}>{icon}</span>
      <span className="flex-1">{children}</span>
      {note && <span className="text-[10px] uppercase tracking-wide text-foreground/30">{note}</span>}
    </>
  );

  if (disabled || !href) {
    return <div className={classes}>{content}</div>;
  }
  return (
    <Link href={href} className={classes}>
      {content}
    </Link>
  );
}

function CompassIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M21 12a8 8 0 1 1-3.2-6.4L21 4l-1 4.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function HistoryIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M3 12a9 9 0 1 0 9-9 9 9 0 0 0-9 9Z" />
      <path d="M12 7v5l3 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function ChartIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M4 20V10M12 20V4M20 20v-7" strokeLinecap="round" />
    </svg>
  );
}
