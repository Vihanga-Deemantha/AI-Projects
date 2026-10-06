"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getMe, getStoredUser, logout, onUserUpdated } from "@/lib/auth";
import { faceSrc, getCompanion } from "@/lib/characters";
import ThemeToggle from "@/components/ThemeToggle";
import UserAvatar from "@/components/UserAvatar";

/**
 * Persistent left rail for every authenticated screen (Practice / Progress / History / Profile).
 * It is rendered once, by components/AppShell.js, which owns whether the drawer is open.
 *
 * Renders two things:
 *  - A `lg:hidden` top bar for phone/tablet widths (menu, logo, avatar).
 *  - The rail itself: `lg:sticky lg:top-0 lg:h-screen` on large screens, so it
 *    stays pinned in view (profile/logout never scroll out of reach) instead
 *    of stretching to match a taller main column and scrolling away with it;
 *    below `lg` it becomes a `fixed` off-canvas drawer toggled by the top bar.
 *
 * A closed drawer is only slid off-screen, which on its own would leave its links reachable with
 * Tab, so it is `inert` until opened. Open, it takes focus, closes on Escape, on a click outside
 * or on any link, and hands focus back to the button that opened it.
 */
export default function AppSidebar({ open, onOpenChange, isDesktop }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState(null);
  const menuButtonRef = useRef(null);
  const closeButtonRef = useRef(null);
  const wasOpenRef = useRef(false);

  // Read after mount: localStorage isn't available during SSR, and reading it
  // during render would mismatch the server-rendered output on hydration.
  // Also subscribe to in-tab edits (e.g. from /profile or the companion
  // picker) so the avatar/name/companion here don't go stale.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is client-only; reading it during render would mismatch SSR output
    setUser(getStoredUser());
    const unsubscribe = onUserUpdated(setUser);
    // Refresh the cached copy from the server (it broadcasts through
    // onUserUpdated), so fields added since this browser last signed in —
    // e.g. email_verified — are present. A failure is harmless: a 401 already
    // redirects to /login by itself.
    getMe().catch(() => {});
    return unsubscribe;
  }, []);

  // Opening the drawer moves focus into it; closing it hands focus back to the menu button.
  useEffect(() => {
    if (open) closeButtonRef.current?.focus();
    else if (wasOpenRef.current) menuButtonRef.current?.focus();
    wasOpenRef.current = open;
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onOpenChange]);

  const close = () => onOpenChange(false);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  const label = user?.display_name || user?.email || "Account";
  const companion = getCompanion(user?.preferred_voice);

  return (
    <>
      {/* Mobile / tablet top bar. Inert while the drawer is open: the drawer is then the only thing to reach. */}
      <header className="flex items-center justify-between border-b border-panel-border bg-panel px-4 py-3 lg:hidden" inert={open}>
        <button
          ref={menuButtonRef}
          type="button"
          onClick={() => onOpenChange(true)}
          aria-label="Open menu"
          aria-expanded={open}
          aria-controls="app-sidebar"
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
      {open && <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={close} aria-hidden="true" />}

      <aside
        id="app-sidebar"
        inert={!isDesktop && !open}
        className={`fixed inset-y-0 left-0 z-50 flex w-64 -translate-x-full flex-col gap-5.5 overflow-y-auto border-r border-panel-border bg-panel px-4.5 py-6 transition-transform duration-200 motion-reduce:transition-none lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:w-58 lg:shrink-0 lg:translate-x-0 ${
          open ? "translate-x-0" : ""
        }`}
      >
        <div className="flex items-center justify-between">
          <Link href="/" onClick={close} className="flex items-center gap-2.5">
            <span className="grid h-7 w-7 place-items-center bg-brand font-display text-sm font-bold text-on-brand">A</span>
            <span className="font-display text-lg font-bold tracking-[0.16em]">AURA</span>
          </Link>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={close}
            aria-label="Close menu"
            className="flex h-8 w-8 cursor-pointer items-center justify-center text-mute transition hover:bg-brand-soft lg:hidden"
          >
            <XIcon className="h-4.5 w-4.5" />
          </button>
        </div>

        <nav aria-label="Main" className="flex flex-col gap-0.5">
          <NavItem href="/practice" active={pathname === "/practice"} onNavigate={close}>Practice</NavItem>
          <NavItem href="/progress" active={pathname === "/progress"} onNavigate={close}>Progress</NavItem>
          <NavItem href="/history" active={pathname.startsWith("/history")} onNavigate={close}>History</NavItem>
          <NavItem href="/profile" active={pathname === "/profile"} onNavigate={close}>Profile</NavItem>
        </nav>

        <div className="mt-auto flex flex-col gap-3">
          <div className="bg-brand-soft p-3.5">
            <div className="text-[10px] font-bold tracking-[0.2em] text-soft uppercase">Today&apos;s companion</div>
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

          {user && user.has_password && user.email_verified === false && (
            <Link
              href="/verify-email"
              className="border border-brand bg-brand-soft px-3.5 py-3 text-xs leading-snug transition hover:bg-brand hover:text-on-brand"
            >
              <span className="block text-[10px] font-bold tracking-[0.18em] uppercase">Verify your email</span>
              <span className="mt-1 block">Confirm it to protect your account.</span>
            </Link>
          )}

          <ThemeToggle className="w-full" />

          <div className="flex items-center gap-2.5 border-t border-panel-border pt-3.5">
            <Link href="/profile" onClick={close} className="shrink-0" aria-label="Your profile">
              <UserAvatar
                user={user}
                className={`h-8 w-8 text-[13px] ${pathname === "/profile" ? "ring-2 ring-foreground" : ""}`}
              />
            </Link>
            <div className="min-w-0 flex-1">
              <Link href="/profile" onClick={close} className="block truncate text-[12.5px] font-bold transition hover:text-brand">
                {label}
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="cursor-pointer text-xs text-mute transition hover:text-brand"
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

function NavItem({ href, active, onNavigate, children }) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={`flex w-full items-center gap-2.5 px-3 py-2.75 text-[13px] transition ${
        active ? "bg-brand-soft font-bold" : "font-medium hover:bg-brand-soft/60"
      }`}
    >
      <span className={`h-4 w-0.75 ${active ? "bg-brand" : "bg-transparent"}`} />
      <span className="flex-1 text-left">{children}</span>
    </Link>
  );
}

function MenuIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" {...props}>
      <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
    </svg>
  );
}
function XIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" {...props}>
      <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
    </svg>
  );
}
