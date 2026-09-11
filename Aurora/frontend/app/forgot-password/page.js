"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { forgotPassword, verifyOTP } from "@/lib/auth";
import OTPInput from "@/components/OTPInput";

const OTP_SECONDS = 15 * 60;

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState(1); // 1: email, 2: otp, 3: new password
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [otpError, setOtpError] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(OTP_SECONDS);
  // Bumped to remount OTPInput (clearing its boxes) on resend/error. State,
  // not a ref, because it's read in the render body via `key={otpAttempt}` —
  // a ref read during render doesn't reliably trigger the remount.
  const [otpAttempt, setOtpAttempt] = useState(0);

  useEffect(() => {
    if (step !== 2) return;
    const id = setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [step]);

  async function handleSendCode(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await forgotPassword(email);
    } catch {
      /* Deliberately ignored — the backend always returns success here to
         avoid revealing which emails have accounts, so the UI always
         advances regardless of what actually happened server-side. */
    } finally {
      setSubmitting(false);
      setSecondsLeft(OTP_SECONDS);
      setStep(2);
    }
  }

  async function handleOtpComplete(code) {
    setOtp(code);
    setOtpError(false);
    // Just collect the code here — actual verification happens with the new
    // password in step 3, since the backend's verify-otp endpoint sets the
    // password in the same call.
    setStep(3);
  }

  async function handleResend() {
    setError(null);
    setOtpAttempt((n) => n + 1);
    try {
      await forgotPassword(email);
    } catch {
      /* same as above — always advance */
    }
    setSecondsLeft(OTP_SECONDS);
  }

  async function handleResetPassword(e) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setSubmitting(true);
    try {
      await verifyOTP({ email, otp, newPassword: password });
      router.replace("/practice");
    } catch (err) {
      setError(err.message);
      setOtpError(true);
      setStep(2);
      setOtpAttempt((n) => n + 1);
      setOtp("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-1 items-center justify-center px-4 py-10 sm:px-6 sm:py-12">
      <div className="w-full max-w-sm">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-linear-to-br from-brand to-brand-dark font-display font-bold text-white">
            A
          </span>
          <span className="font-display text-lg font-bold">AURA</span>
        </Link>

        <div className="rounded-2xl border border-panel-border bg-panel p-5 shadow-sm sm:p-7">
          <StepDots current={step} />

          {error && (
            <div role="alert" className="mb-4 rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-sm text-rose-500">
              {error}
            </div>
          )}

          {step === 1 && (
            <div key="step1" className="aura-step-enter">
              <h1 className="font-display text-2xl font-bold">Forgot your password?</h1>
              <p className="mt-2 mb-6 text-sm text-foreground/50">
                Enter your email and we&apos;ll send you a 6-digit code.
              </p>
              <form onSubmit={handleSendCode} className="flex flex-col gap-4">
                <input
                  type="email" required autoFocus value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="rounded-[13px] border border-panel-border bg-foreground/5 px-4 py-3.5 text-sm outline-none transition placeholder:text-foreground/30 focus:border-brand focus:ring-4 focus:ring-brand/15"
                />
                <button
                  type="submit" disabled={submitting}
                  className="rounded-full bg-linear-to-br from-brand to-brand-dark px-4 py-3.75 font-display text-[15px] font-bold text-white shadow-lg shadow-brand/25 transition hover:brightness-110 disabled:opacity-50"
                >
                  {submitting ? "Sending…" : "Send Code"}
                </button>
              </form>
            </div>
          )}

          {step === 2 && (
            <div key="step2" className="aura-step-enter flex flex-col items-center text-center">
              <h1 className="font-display text-2xl font-bold">Enter the code</h1>
              <p className="mt-2 mb-2 text-sm text-foreground/50">
                If that email is registered, a 6-digit code is on its way to<br />
                <span className="font-medium text-foreground">{email}</span>
              </p>
              <CountdownRing secondsLeft={secondsLeft} total={OTP_SECONDS} />
              <div className="mt-5 mb-4 w-full">
                <OTPInput key={otpAttempt} onComplete={handleOtpComplete} error={otpError} />
              </div>
              <button
                type="button" onClick={handleResend} disabled={secondsLeft > 0}
                className="text-sm font-medium text-brand transition hover:underline disabled:cursor-not-allowed disabled:text-foreground/30 disabled:no-underline"
              >
                Resend code
              </button>
            </div>
          )}

          {step === 3 && (
            <div key="step3" className="aura-step-enter">
              <h1 className="font-display text-2xl font-bold">Set a new password</h1>
              <p className="mt-2 mb-6 text-sm text-foreground/50">Choose a new password for your account.</p>
              <form onSubmit={handleResetPassword} className="flex flex-col gap-4">
                <input
                  type="password" required autoFocus minLength={8} value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  className="rounded-[13px] border border-panel-border bg-foreground/5 px-4 py-3.5 text-sm outline-none transition placeholder:text-foreground/30 focus:border-brand focus:ring-4 focus:ring-brand/15"
                />
                <input
                  type="password" required value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Confirm password"
                  className="rounded-[13px] border border-panel-border bg-foreground/5 px-4 py-3.5 text-sm outline-none transition placeholder:text-foreground/30 focus:border-brand focus:ring-4 focus:ring-brand/15"
                />
                <button
                  type="submit" disabled={submitting}
                  className="rounded-full bg-linear-to-br from-brand to-brand-dark px-4 py-3.75 font-display text-[15px] font-bold text-white shadow-lg shadow-brand/25 transition hover:brightness-110 disabled:opacity-50"
                >
                  {submitting ? "Resetting…" : "Reset Password"}
                </button>
              </form>
            </div>
          )}
        </div>

        <p className="mt-5 text-center text-sm text-foreground/50">
          Remembered it? <Link href="/login" className="font-medium text-brand hover:underline">Log in</Link>
        </p>
      </div>
    </div>
  );
}

function StepDots({ current }) {
  return (
    <div className="mb-6 flex items-center justify-center gap-2">
      {[1, 2, 3].map((n) => (
        <span
          key={n}
          className={`h-1.5 rounded-full transition-all ${
            n === current ? "w-6 bg-brand" : n < current ? "w-1.5 bg-brand/50" : "w-1.5 bg-panel-border"
          }`}
        />
      ))}
    </div>
  );
}

function CountdownRing({ secondsLeft, total }) {
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  const progress = secondsLeft / total;
  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
  const ss = String(secondsLeft % 60).padStart(2, "0");

  return (
    <div className="relative flex h-18 w-18 items-center justify-center">
      <svg width="72" height="72" className="-rotate-90">
        <circle cx="36" cy="36" r={radius} fill="none" stroke="currentColor" className="text-panel-border" strokeWidth="4" />
        <circle
          cx="36" cy="36" r={radius} fill="none" stroke="currentColor" className="text-brand" strokeWidth="4"
          strokeLinecap="round" strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - progress)}
          style={{ transition: "stroke-dashoffset 1s linear" }}
        />
      </svg>
      <span className="absolute font-display text-xs font-bold">{mm}:{ss}</span>
    </div>
  );
}
