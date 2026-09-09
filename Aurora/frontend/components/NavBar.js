"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getStoredUser, logout } from "@/lib/auth";

/** App navigation for signed-in pages (Practice / History + account). */
export default function NavBar() {
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

  return (
    <header className="flex items-center justify-between border-b border-panel-border bg-panel/70 px-6 py-3">
      <div className="flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand text-sm font-bold text-white">
            A
          </span>
          <span className="font-bold">AURA</span>
        </Link>
        <nav className="flex items-center gap-1">
          <NavLink href="/practice" active={pathname === "/practice"}>Practice</NavLink>
          <NavLink href="/history" active={pathname.startsWith("/history")}>History</NavLink>
        </nav>
      </div>

      <div className="flex items-center gap-3">
        <span className="hidden text-sm text-foreground/50 sm:inline">{label}</span>
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-xl border border-panel-border px-3 py-1.5 text-sm font-medium text-foreground/70 transition hover:border-brand/40 hover:text-brand"
        >
          Log out
        </button>
      </div>
    </header>
  );
}

function NavLink({ href, active, children }) {
  return (
    <Link
      href={href}
      className={`rounded-xl px-3 py-1.5 text-sm font-medium transition ${
        active ? "bg-brand/10 text-brand" : "text-foreground/70 hover:text-brand"
      }`}
    >
      {children}
    </Link>
  );
}
