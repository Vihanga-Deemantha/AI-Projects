"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { login, signup } from "@/lib/auth";

/**
 * Shared login/signup form. `mode` is "login" or "signup".
 *
 * Password minimum is 8 to match the server's validation — checking it here
 * too gives instant feedback instead of a round trip, but the server remains
 * the actual enforcement point.
 */
export default function AuthForm({ mode }) {
  const isSignup = mode === "signup";
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

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
    <div className="flex min-h-screen flex-1 items-center justify-center px-6 py-12">
      <div className="w-full max-w-sm">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand font-bold text-white">
            A
          </span>
          <span className="text-lg font-bold">AURA</span>
        </Link>

        <div className="rounded-2xl border border-panel-border bg-panel p-6 shadow-sm">
          <h1 className="text-xl font-bold">
            {isSignup ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mt-1 mb-6 text-sm text-foreground/50">
            {isSignup
              ? "Start practising spoken English with feedback."
              : "Log in to continue practising."}
          </p>

          {error && (
            <div
              role="alert"
              className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700"
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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

            <Field
              label="Password" type="password" value={password} onChange={setPassword}
              autoComplete={isSignup ? "new-password" : "current-password"}
              required minLength={isSignup ? 8 : undefined}
              placeholder={isSignup ? "At least 8 characters" : "Your password"}
            />

            <button
              type="submit"
              disabled={submitting}
              className="mt-1 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting
                ? isSignup ? "Creating account…" : "Logging in…"
                : isSignup ? "Sign Up" : "Log In"}
            </button>
          </form>
        </div>

        <p className="mt-5 text-center text-sm text-foreground/50">
          {isSignup ? "Already have an account? " : "Don't have an account? "}
          <Link
            href={isSignup ? "/login" : "/signup"}
            className="font-medium text-brand hover:underline"
          >
            {isSignup ? "Log in" : "Sign up"}
          </Link>
        </p>
      </div>
    </div>
  );
}

function Field({ label, type, value, onChange, ...rest }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-foreground/40">
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-xl border border-panel-border bg-white px-3 py-2.5 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
        {...rest}
      />
    </label>
  );
}
