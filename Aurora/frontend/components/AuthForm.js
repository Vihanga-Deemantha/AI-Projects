"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { login, signup } from "@/lib/auth";

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

      <form onSubmit={handleSubmit} className="flex flex-col gap-[18px]">
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
          className="mt-1 rounded-full bg-linear-to-br from-brand to-brand-dark px-4 py-[15px] font-display text-[15px] font-bold text-white shadow-lg shadow-brand/25 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
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
