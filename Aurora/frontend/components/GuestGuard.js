"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getMe, isLoggedIn } from "@/lib/auth";

/**
 * Wraps the login/signup pages: someone who is already signed in has no
 * business on them, so send them to practice. The token is verified with the
 * server first — a stale one is cleared by getMe() and the form stays put,
 * instead of bouncing the user into a page that would immediately fail.
 *
 * The form renders straight away (no "checking" blank state) so signed-out
 * visitors, the common case, see no delay.
 */
export default function GuestGuard({ children }) {
  const router = useRouter();

  useEffect(() => {
    if (!isLoggedIn()) return;
    let cancelled = false;
    getMe()
      .then(() => {
        if (!cancelled) router.replace("/practice");
      })
      .catch(() => {
        /* stale token — already cleared; stay on the form */
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  return children;
}
