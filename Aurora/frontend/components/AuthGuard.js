"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/auth";

/**
 * Gates a page behind login. Renders nothing until the check has run, so
 * protected content never flashes on screen before the redirect.
 *
 * This is a UX guard, not a security boundary — the real enforcement is
 * server-side (every protected endpoint requires a valid JWT), so a user
 * bypassing this in the browser still can't read or write any data.
 */
export default function AuthGuard({ children }) {
  const router = useRouter();
  const [status, setStatus] = useState("checking"); // checking | allowed

  useEffect(() => {
    if (isLoggedIn()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is client-only; reading it during render would mismatch SSR output
      setStatus("allowed");
    } else {
      router.replace("/login");
    }
  }, [router]);

  if (status !== "allowed") {
    return (
      <div className="flex min-h-screen flex-1 items-center justify-center text-sm text-foreground/40">
        Loading…
      </div>
    );
  }

  return children;
}
