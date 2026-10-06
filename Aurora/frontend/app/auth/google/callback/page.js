"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { completeGoogleSignIn } from "@/lib/auth";

/**
 * Lands here after backend/routers/google.py's callback redirects the browser
 * back with ?code=... — a single-use code that completeGoogleSignIn() trades
 * for a real session. Nothing to render beyond a brief loading state.
 */
export default function GoogleCallbackPage() {
  const router = useRouter();
  // The code can only be redeemed once, and completeGoogleSignIn() strips it
  // from the URL as a side effect. React's dev Strict Mode runs effects twice;
  // without this guard the second run would find no code, report a failure,
  // and overwrite the first run's redirect to /practice.
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;
    completeGoogleSignIn().then(({ user, next }) => {
      router.replace(user ? next : "/login?error=google_failed");
    });
  }, [router]);

  return (
    <div className="flex min-h-screen flex-1 flex-col items-center justify-center gap-4">
      <div className="h-10 w-10 animate-spin rounded-full border-2 border-panel-border border-t-brand" />
      <p className="text-sm text-mute">Signing you in…</p>
    </div>
  );
}
