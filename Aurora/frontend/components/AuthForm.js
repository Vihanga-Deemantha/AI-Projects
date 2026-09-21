"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getGoogleAuthUrl, login, signup, startGoogleAuth } from "@/lib/auth";
import { useAuthShell } from "@/components/AuthShell";

const GOOGLE_ERROR_MESSAGES = {
  google_not_configured: "Google sign-in isn't set up on this server yet.",
  google_failed: "Google sign-in didn't complete. Please try again.",
  session_expired: "Your session expired. Please sign in again.",
};

export const authInput =
  "h-13 w-full border border-transparent bg-field px-4 text-[14.5px] text-foreground outline-none transition focus:border-brand";
export const authLabel = "mb-1.75 block text-[11px] font-bold tracking-[0.14em] text-soft uppercase";
export const authPrimary =
  "h-13 w-full cursor-pointer bg-foreground text-[11px] font-bold tracking-[0.2em] text-background uppercase transition hover:bg-brand hover:text-on-brand disabled:cursor-not-allowed disabled:opacity-50";

/**
 * Shared login/signup form column. `mode` is "login" or "signup". Renders
 * just the form itself — the split-card shell (companion panel + this
 * column) lives in components/AuthShell.js and wraps it from
 * app/login/page.js and app/signup/page.js.
 *
 * Password minimum is 8 to match the server's validation — checking it here
 * too gives instant feedback instead of a round trip, but the server remains
 * the actual enforcement point.
 */
export default function AuthForm({ mode }) {
  const isSignup = mode === "signup";
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setLookAway } = useAuthShell();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // A failed Google OAuth attempt redirects back here with ?error=...
  useEffect(() => {
    const code = searchParams.get("error");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time sync from the URL after a server-side redirect, not derived from props/state
    if (code) setError(GOOGLE_ERROR_MESSAGES[code] || "Something went wrong. Please try again.");
  }, [searchParams]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (isSignup && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setSubmitting(true);
    try {
      if (isSignup) {
        await signup({ email, password, displayName });
      } else {
        await login({ email, password });
      }
      router.replace("/practice");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full">
      <h1 className="mt-7.5 text-center font-display text-[clamp(30px,3.4vw,42px)] leading-[1.02] font-bold">
        {isSignup ? "Start speaking" : "Welcome back"}
      </h1>
      <p className="mt-3 text-center text-sm leading-[1.55] text-soft">
        {isSignup
          ? "Six companions, seven scenarios. Setting up takes about a minute."
          : "Enter your email and password to pick up where you left off."}
      </p>

      {error && (
        <div role="alert" className="mt-6 border border-brand bg-brand-soft px-3.5 py-2.5 text-[13px] text-foreground">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-7.5 flex flex-col gap-4">
        {isSignup && (
          <label className="block">
            <span className={authLabel}>Name (optional)</span>
            <input
              type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)}
              autoComplete="nickname" placeholder="What should they call you?" className={authInput}
            />
          </label>
        )}

        <label className="block">
          <span className={authLabel}>Email</span>
          <input
            type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            autoComplete="email" required placeholder="Enter your email" className={authInput}
          />
        </label>

        <label className="block">
          <span className={authLabel}>Password</span>
          <span className="relative block">
            <input
              type={showPw ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={isSignup ? "new-password" : "current-password"}
              required minLength={isSignup ? 8 : undefined}
              placeholder={isSignup ? "At least 8 characters" : "Enter your password"}
              onFocus={() => setLookAway(!showPw)}
              onBlur={() => setLookAway(false)}
              className={`${authInput} pr-19.5`}
            />
            <button
              type="button"
              onClick={() => { setShowPw((v) => !v); setLookAway(false); }}
              className="absolute top-0 right-0 h-full cursor-pointer px-4 text-[10px] font-bold tracking-[0.14em] text-soft uppercase transition hover:text-brand"
            >
              {showPw ? "Hide" : "Show"}
            </button>
          </span>
        </label>

        {!isSignup && (
          <div className="-mt-1 text-right">
            <Link href="/forgot-password" className="text-[12.5px] font-semibold text-soft transition hover:text-brand">
              Forgot password
            </Link>
          </div>
        )}

        <button type="submit" disabled={submitting} className={`${authPrimary} mt-1.5`}>
          {submitting
            ? isSignup ? "Creating account…" : "Signing in…"
            : isSignup ? "Create account" : "Sign in"}
        </button>
      </form>

      <div className="my-5.5 flex items-center gap-3.5">
        <span className="h-px flex-1 bg-panel-border" />
        <span className="text-[10px] font-bold tracking-[0.2em] text-mute uppercase">or</span>
        <span className="h-px flex-1 bg-panel-border" />
      </div>

      <a
        href={getGoogleAuthUrl()}
        onClick={(e) => startGoogleAuth(e, { onError: setError })}
        className="flex h-12.5 items-center justify-center gap-2.75 border border-panel-border text-[13px] font-semibold transition hover:border-brand"
      >
        <GoogleIcon className="h-4.25 w-4.25" />
        {isSignup ? "Sign up with Google" : "Sign in with Google"}
      </a>

      <p className="mt-6.5 text-center">
        <Link href="/" className="text-[10px] font-semibold tracking-[0.12em] text-mute uppercase transition hover:text-brand">
          &larr; Back to AURA
        </Link>
      </p>
      <p className="mt-3.5 text-center text-[13px] text-soft">
        {isSignup ? "Already have an account?" : "Don't have an account?"}
        <Link
          href={isSignup ? "/login" : "/signup"}
          className="ml-1.5 font-bold text-foreground underline underline-offset-[3px] transition hover:text-brand"
        >
          {isSignup ? "Sign in" : "Sign up"}
        </Link>
      </p>
    </div>
  );
}

function GoogleIcon(props) {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" {...props}>
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.5l6.8-6.8C35.6 2.3 30.2 0 24 0 14.6 0 6.5 5.4 2.5 13.3l7.9 6.1C12.3 13.5 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-2.8-.4-4.1H24v8.4h12.5c-.3 2.1-1.6 5.2-4.6 7.3l7.7 6c4.6-4.2 6.5-10.3 6.5-17.6z" />
      <path fill="#FBBC05" d="M10.4 28.6c-.5-1.5-.8-3-.8-4.6s.3-3.1.8-4.6l-7.9-6.1C.9 16.5 0 20.1 0 24s.9 7.5 2.5 10.7l7.9-6.1z" />
      <path fill="#34A853" d="M24 48c6.2 0 11.5-2 15.3-5.6l-7.7-6c-2.1 1.4-4.8 2.3-7.6 2.3-6.3 0-11.7-4-13.6-9.9l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
    </svg>
  );
}
