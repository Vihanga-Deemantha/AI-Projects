"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getGoogleAuthUrl, login, signup } from "@/lib/auth";

const GOOGLE_ERROR_MESSAGES = {
  google_not_configured: "Google sign-in isn't set up on this server yet.",
  google_failed: "Google sign-in didn't complete. Please try again.",
};

/**
 * Shared login/signup form column. `mode` is "login" or "signup". Renders
 * just the form itself — the enclosing split-panel shell (brand/orb panel +
 * this column) lives in app/login/page.js and app/signup/page.js.
 *
 * Password minimum is 8 to match the server's validation — checking it here
 * too gives instant feedback instead of a round trip, but the server remains
 * the actual enforcement point.
 */
export default function AuthForm({ mode }) {
  const isSignup = mode === "signup";
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
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
    <div className="w-full max-w-sm">
      <h1 className="font-display text-3xl font-bold">
        {isSignup ? "Create your account" : "Welcome back"}
      </h1>
      <p className="mt-2 mb-8 text-[14.5px] text-foreground/50">
        {isSignup
          ? "Start practising spoken English with feedback that sticks."
          : "Log in to continue practising."}
      </p>

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-sm text-rose-500"
        >
          {error}
        </div>
      )}

      <a
        href={getGoogleAuthUrl()}
        className="flex items-center justify-center gap-2.5 rounded-full border border-panel-border bg-foreground/5 px-4 py-3.5 text-sm font-semibold transition hover:bg-foreground/10"
      >
        <GoogleIcon className="h-4.5 w-4.5" />
        Continue with Google
      </a>

      <div className="my-6 flex items-center gap-3 text-xs font-medium text-foreground/35">
        <span className="h-px flex-1 bg-panel-border" />
        or
        <span className="h-px flex-1 bg-panel-border" />
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4.5">
        <Field
          label="Email" type="email" value={email} onChange={setEmail}
          autoComplete="email" required placeholder="you@example.com"
        />

        {isSignup && (
          <Field
            label="Display name (optional)" type="text" value={displayName}
            onChange={setDisplayName} autoComplete="nickname" placeholder="How should we greet you?"
          />
        )}

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wide text-foreground/40">Password</span>
            {!isSignup && (
              <Link href="/forgot-password" className="text-[11.5px] font-semibold text-brand hover:underline">
                Forgot?
              </Link>
            )}
          </div>
          <input
            type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete={isSignup ? "new-password" : "current-password"}
            required minLength={isSignup ? 8 : undefined}
            placeholder={isSignup ? "At least 8 characters" : "Your password"}
            className="rounded-[13px] border border-panel-border bg-foreground/5 px-4 py-3.5 text-sm outline-none transition placeholder:text-foreground/30 focus:border-brand focus:ring-4 focus:ring-brand/15"
          />
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="mt-1 rounded-full bg-linear-to-br from-brand to-brand-dark px-4 py-3.75 font-display text-[15px] font-bold text-white shadow-lg shadow-brand/25 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting
            ? isSignup ? "Creating account…" : "Logging in…"
            : isSignup ? "Sign Up" : "Log In"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-foreground/50">
        {isSignup ? "Already have an account? " : "Don't have an account? "}
        <Link
          href={isSignup ? "/login" : "/signup"}
          className="font-medium text-brand hover:underline"
        >
          {isSignup ? "Log in" : "Sign up"}
        </Link>
      </p>
    </div>
  );
}

function Field({ label, type, value, onChange, ...rest }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-[11px] font-bold uppercase tracking-wide text-foreground/40">
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-[13px] border border-panel-border bg-foreground/5 px-4 py-3.5 text-sm outline-none transition placeholder:text-foreground/30 focus:border-brand focus:ring-4 focus:ring-brand/15"
        {...rest}
      />
    </label>
  );
}

function GoogleIcon(props) {
  return (
    <svg viewBox="0 0 48 48" {...props}>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 15.9 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6 29.6 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.5 0 10.5-2.1 14.3-5.6l-6.6-5.6C29.6 34.6 26.9 35.5 24 35.5c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.6 39.6 16.3 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.2 4.3-4.1 5.7l6.6 5.6C41.7 36.1 44 30.5 44 24c0-1.3-.1-2.7-.4-3.5z" />
    </svg>
  );
}
