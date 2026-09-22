"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getStoredUser, logout, onUserUpdated } from "@/lib/auth";
import { faceSrc, getCompanion } from "@/lib/characters";
import ThemeToggle from "@/components/ThemeToggle";
import UserAvatar from "@/components/UserAvatar";

/**
 * Persistent left rail for every authenticated screen (Practice / History /
 * Profile).
 *
 * Renders two things:
 *  - A `lg:hidden` top bar for phone/tablet widths (menu, logo, avatar).
 *  - The rail itself: `lg:sticky lg:top-0 lg:h-screen` on large screens, so it
 *    stays pinned in view (profile/logout never scroll out of reach) instead
 *    of stretching to match a taller main column and scrolling away with it;
 *    below `lg` it becomes a `fixed` off-canvas drawer toggled by the top bar.
 *
 * Self-contained: the parent page just renders <AppSidebar /> followed by
 * its main content inside a `flex flex-col lg:flex-row` wrapper.
 */
export default function AppSidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState(null);
  const [open, setOpen] = useState(false);

  // Read after mount: localStorage isn't available during SSR, and reading it
  // during render would mismatch the server-rendered output on hydration.
  // Also subscribe to in-tab edits (e.g. from /profile or the companion
  // picker) so the avatar/name/companion here don't go stale.
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
  const companion = getCompanion(user?.preferred_voice);

  return (
    <>
      {/* Mobile / tablet top bar */}
      <header className="flex items-center justify-between border-b border-panel-border bg-panel px-4 py-3 lg:hidden">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open menu"
          className="flex h-9 w-9 cursor-pointer items-center justify-center text-soft transition hover:bg-brand-soft"
        >
          <MenuIcon className="h-5 w-5" />
        </button>
        <Link href="/" className="flex items-center gap-2.5">
          <span className="grid h-7 w-7 place-items-center bg-brand font-display text-sm font-bold text-on-brand">A</span>
          <span className="font-display text-base font-bold tracking-[0.16em]">AURA</span>
        </Link>
        <Link href="/profile" className="shrink-0" aria-label="Your profile">
          <UserAvatar user={user} className="h-8 w-8 text-[13px]" />
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
        className={`fixed inset-y-0 left-0 z-50 flex w-64 -translate-x-full flex-col gap-5.5 overflow-y-auto border-r border-panel-border bg-panel px-4.5 py-6 transition-transform duration-200 lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:w-58 lg:shrink-0 lg:translate-x-0 ${
          open ? "translate-x-0" : ""
        }`}
      >
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="grid h-7 w-7 place-items-center bg-brand font-display text-sm font-bold text-on-brand">A</span>
            <span className="font-display text-lg font-bold tracking-[0.16em]">AURA</span>
          </Link>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close menu"
            className="flex h-8 w-8 cursor-pointer items-center justify-center text-mute transition hover:bg-brand-soft lg:hidden"
          >
            <XIcon className="h-4.5 w-4.5" />
          </button>
        </div>

        <nav className="flex flex-col gap-0.5">
          <NavItem href="/practice" active={pathname === "/practice"}>Practice</NavItem>
          <NavItem href="/history" active={pathname.startsWith("/history")}>History</NavItem>
          <NavItem href="/profile" active={pathname === "/profile"}>Profile</NavItem>
          <NavItem disabled note="Soon">Progress</NavItem>
        </nav>

        <div className="mt-auto flex flex-col gap-3">
          <div className="bg-brand-soft p-3.5">
            <div className="text-[9.5px] font-bold tracking-[0.2em] text-soft uppercase">Today&apos;s companion</div>
            <div className="mt-3 flex items-center gap-3">
              <div
                role="img"
                aria-label={companion.name}
                className="h-10.5 w-10.5 flex-none rounded-full bg-panel bg-cover bg-top ring-2 ring-brand"
                style={{ backgroundImage: `url('${faceSrc(companion.id, "smiling")}')` }}
              />
              <div className="min-w-0">
                <div className="font-display text-base leading-none font-bold">{companion.name}</div>
                <div className="mt-0.75 text-[10px] font-bold tracking-[0.14em] text-soft uppercase">{companion.tag}</div>
              </div>
            </div>
          </div>

          <ThemeToggle className="w-full" />

          <div className="flex items-center gap-2.5 border-t border-panel-border pt-3.5">
            <Link href="/profile" className="shrink-0" aria-label="Your profile">
              <UserAvatar
                user={user}
                className={`h-8 w-8 text-[13px] ${pathname === "/profile" ? "ring-2 ring-foreground" : ""}`}
              />
            </Link>
            <div className="min-w-0 flex-1">
              <Link href="/profile" className="block truncate text-[12.5px] font-bold transition hover:text-brand">
                {label}
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="cursor-pointer text-[11px] text-mute transition hover:text-brand"
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

function NavItem({ href, active, disabled, note, children }) {
  const classes = `flex w-full items-center gap-2.5 px-3 py-2.75 text-[13px] transition ${
    active
      ? "bg-brand-soft font-bold"
      : disabled
        ? "cursor-not-allowed font-medium text-mute"
        : "font-medium hover:bg-brand-soft/60"
  }`;

  const content = (
    <>
      <span className={`h-4 w-0.75 ${active ? "bg-brand" : "bg-transparent"}`} />
      <span className="flex-1 text-left">{children}</span>
      {note && <span className="text-[9px] font-bold tracking-[0.14em] text-mute uppercase">{note}</span>}
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
