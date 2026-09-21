"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { forgotPassword, verifyOTP } from "@/lib/auth";
import AuthShell from "@/components/AuthShell";
import OTPInput from "@/components/OTPInput";
import { authInput, authLabel, authPrimary } from "@/components/AuthForm";

const OTP_SECONDS = 15 * 60;

export default function ForgotPasswordPage() {
  return (
    <AuthShell>
      <ResetFlow />
    </AuthShell>
  );
}

function ResetFlow() {
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

  const heading = step === 1 ? "Forgot your password?" : step === 2 ? "Enter the code" : "Set a new password";
  const sub =
    step === 1
      ? "Enter your email and we will send a six-digit code."
      : step === 2
        ? `If that email is registered, a code is on its way to ${email || "your inbox"}.`
        : "Choose a new password for your account.";

  return (
    <div className="w-full">
      <div className="mt-6.5 flex items-center justify-center gap-1.75">
        {[1, 2, 3].map((n) => (
          <span
            key={n}
            className={`h-1.75 transition-[width,background] duration-300 ${
              n === step ? "w-6 bg-brand" : n < step ? "w-1.75 bg-soft" : "w-1.75 bg-panel-border"
            }`}
          />
        ))}
      </div>

      <h1 className="mt-7.5 text-center font-display text-[clamp(30px,3.4vw,42px)] leading-[1.02] font-bold">{heading}</h1>
      <p className="mt-3 text-center text-sm leading-[1.55] text-soft">{sub}</p>

      {error && (
        <div role="alert" className="mt-6 border border-brand bg-brand-soft px-3.5 py-2.5 text-[13px] text-foreground">
          {error}
        </div>
      )}

      {step === 1 && (
        <form key="step1" onSubmit={handleSendCode} className="aura-step-enter mt-7.5 flex flex-col gap-4">
          <label className="block">
            <span className={authLabel}>Email</span>
            <input
              type="email" required autoFocus value={email} autoComplete="email"
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com" className={authInput}
            />
          </label>
          <button type="submit" disabled={submitting} className={`${authPrimary} mt-1.5`}>
            {submitting ? "Sending…" : "Send code"}
          </button>
        </form>
      )}

      {step === 2 && (
        <div key="step2" className="aura-step-enter mt-6.5 flex flex-col items-center gap-5">
          <CountdownRing secondsLeft={secondsLeft} total={OTP_SECONDS} />
          <OTPInput key={otpAttempt} onComplete={handleOtpComplete} error={otpError} />
          <button
            type="button" onClick={handleResend} disabled={secondsLeft > 0}
            className="cursor-pointer text-[12.5px] font-semibold text-brand transition hover:underline disabled:cursor-not-allowed disabled:text-mute disabled:no-underline"
          >
            {secondsLeft > 0 ? `Resend code in ${Math.ceil(secondsLeft / 60)} min` : "Resend code"}
          </button>
        </div>
      )}

      {step === 3 && (
        <form key="step3" onSubmit={handleResetPassword} className="aura-step-enter mt-7.5 flex flex-col gap-4">
          <label className="block">
            <span className={authLabel}>New password</span>
            <input
              type="password" required autoFocus minLength={8} value={password} autoComplete="new-password"
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters" className={authInput}
            />
          </label>
          <label className="block">
            <span className={authLabel}>Confirm password</span>
            <input
              type="password" required value={confirm} autoComplete="new-password"
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Type it again" className={authInput}
            />
          </label>
          <button type="submit" disabled={submitting} className={`${authPrimary} mt-1.5`}>
            {submitting ? "Resetting…" : "Reset password"}
          </button>
        </form>
      )}

      <p className="mt-6.5 text-center">
        <Link href="/" className="text-[10px] font-semibold tracking-[0.12em] text-mute uppercase transition hover:text-brand">
          &larr; Back to AURA
        </Link>
      </p>
      <p className="mt-3.5 text-center text-[13px] text-soft">
        Remembered it?
        <Link href="/login" className="ml-1.5 font-bold text-foreground underline underline-offset-[3px] transition hover:text-brand">
          Sign in
        </Link>
      </p>
    </div>
  );
}

function CountdownRing({ secondsLeft, total }) {
  const radius = 32;
  const circumference = 2 * Math.PI * radius;
  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
  const ss = String(secondsLeft % 60).padStart(2, "0");

  return (
    <div className="relative grid h-19 w-19 place-items-center">
      <svg width="76" height="76" viewBox="0 0 76 76" className="-rotate-90" aria-hidden="true">
        <circle cx="38" cy="38" r={radius} fill="none" stroke="var(--panel-border)" strokeWidth="4" />
        <circle
          cx="38" cy="38" r={radius} fill="none" stroke="var(--brand)" strokeWidth="4" strokeLinecap="round"
          strokeDasharray={circumference.toFixed(1)}
          strokeDashoffset={(circumference * (1 - secondsLeft / total)).toFixed(1)}
          style={{ transition: "stroke-dashoffset 1s linear" }}
        />
      </svg>
      <span className="absolute font-display text-[13px] font-bold tracking-[0.04em]">{mm}:{ss}</span>
    </div>
  );
}
