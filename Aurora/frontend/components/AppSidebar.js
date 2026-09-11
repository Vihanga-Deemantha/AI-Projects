"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getStoredUser, logout, onUserUpdated } from "@/lib/auth";
import ThemeToggle from "@/components/ThemeToggle";

/**
 * Persistent left navigation for every authenticated screen (Practice /
 * History / Profile).
 *
 * Renders two things:
 *  - A `lg:hidden` top bar for phone/tablet widths (logo, hamburger, avatar).
 *  - The nav itself: `lg:sticky lg:top-0 lg:h-screen` on large screens, so it
 *    stays pinned in view (profile/logout never scroll out of reach) instead
 *    of stretching to match a taller main column and scrolling away with it;
 *    below `lg` it becomes a `fixed` off-canvas drawer toggled by the top bar.
 *
 * Self-contained: the parent page just renders <AppSidebar /> followed by
 * its main content inside a `flex flex-col lg:flex-row` wrapper — no other
 * per-page layout changes needed for the responsive behavior here.
 */
export default function AppSidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState(null);
  const [open, setOpen] = useState(false);

  // Read after mount: localStorage isn't available during SSR, and reading it
  // during render would mismatch the server-rendered output on hydration.
  // Also subscribe to in-tab edits (e.g. from /profile) so the avatar/name
  // here don't go stale without a full navigation remounting this component.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is client-only; reading it during render would mismatch SSR output
    setUser(getStoredUser());
    return onUserUpdated(setUser);
  }, []);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  const label = user?.display_name || user?.email || "Account";
  const initial = (user?.display_name || user?.email || "A").charAt(0).toUpperCase();

  return (
    <>
      {/* Mobile / tablet top bar */}
      <header className="flex items-center justify-between border-b border-panel-border bg-surface px-4 py-3 lg:hidden">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open menu"
          className="flex h-9 w-9 items-center justify-center rounded-xl text-foreground/70 transition hover:bg-foreground/5"
        >
          <MenuIcon className="h-5 w-5" />
        </button>
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-[9px] bg-linear-to-br from-brand to-brand-dark font-display text-xs font-bold text-white">
            A
          </span>
          <span className="font-display text-base font-bold">AURA</span>
        </Link>
        <Link href="/profile" className="shrink-0">
          {user?.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- external Cloudinary/Google CDN URL, not a locally-optimizable asset
            <img src={user.avatar_url} alt="" className="h-8 w-8 rounded-full object-cover ring-1 ring-panel-border" />
          ) : (
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-linear-to-br from-sky-300 to-brand text-xs font-bold text-white">
              {initial}
            </span>
          )}
        </Link>
      </header>

      {/* Backdrop behind the mobile drawer */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-64 -translate-x-full flex-col gap-1.5 overflow-y-auto border-r border-panel-border bg-surface px-4 py-7 transition-transform duration-200 lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:w-56 lg:translate-x-0 ${
          open ? "translate-x-0" : ""
        }`}
      >
        <div className="mb-6 flex items-center justify-between px-2">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-linear-to-br from-brand to-brand-dark font-display text-sm font-bold text-white shadow-[0_0_16px_rgba(139,124,255,0.5)]">
              A
            </span>
            <span className="font-display text-lg font-bold">AURA</span>
          </Link>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close menu"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-foreground/50 transition hover:bg-foreground/5 lg:hidden"
          >
            <XIcon className="h-4.5 w-4.5" />
          </button>
        </div>

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
            <Link href="/profile" className="shrink-0">
              {user?.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element -- external Cloudinary/Google CDN URL, not a locally-optimizable asset
                <img
                  src={user.avatar_url}
                  alt=""
                  className="h-8 w-8 rounded-full object-cover ring-1 ring-panel-border"
                />
              ) : (
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-linear-to-br from-sky-300 to-brand text-xs font-bold text-white">
                  {initial}
                </span>
              )}
            </Link>
            <div className="min-w-0 flex-1">
              <Link href="/profile" className="block truncate text-[13px] font-semibold hover:text-brand">
                {label}
              </Link>
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
    </>
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
      <span className={`h-4.5 w-4.5 ${active ? "text-brand" : ""}`}>{icon}</span>
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
function MenuIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
    </svg>
  );
}
function XIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
    </svg>
  );
}
