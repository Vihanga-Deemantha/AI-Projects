"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { handleGoogleCallback } from "@/lib/auth";

/**
 * Lands here after backend/routers/google.py's callback redirects the
 * browser back with ?token=...&user=.... Pure client-side hop — there's
 * nothing to render beyond a brief loading state.
 */
export default function GoogleCallbackPage() {
  const router = useRouter();
  // handleGoogleCallback() strips the token/user query params as a side
  // effect, so it's only safe to call once. Without this guard, React's dev
  // Strict Mode double-invoking the effect makes the second call see an
  // already-stripped URL, read null, and overwrite the first call's
  // redirect to /practice with a spurious google_failed error.
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;
    const { user, next } = handleGoogleCallback();
    router.replace(user ? next : "/login?error=google_failed");
  }, [router]);

  return (
    <div className="flex min-h-screen flex-1 flex-col items-center justify-center gap-4">
      <div className="h-10 w-10 animate-spin rounded-full border-2 border-panel-border border-t-brand" />
      <p className="text-sm text-foreground/50">Signing you in…</p>
    </div>
  );
}
