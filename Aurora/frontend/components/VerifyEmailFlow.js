"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getMe, resendVerification, verifyEmail } from "@/lib/auth";
import OTPInput from "@/components/OTPInput";

const RESEND_COOLDOWN_SECONDS = 60;

/**
 * "Enter the 6-digit code we emailed you" — confirms the signed-in user owns
 * their email address. Shown right after signup and reachable from the profile
 * page. Nothing in AURA is blocked while unverified; verification protects the
 * account (e.g. so nobody can pre-register your address and later ride along
 * when you sign in with Google).
 */
export default function VerifyEmailFlow() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [phase, setPhase] = useState("loading"); // loading | entry | submitting | done
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [otpError, setOtpError] = useState(false);
  // Bumped to remount OTPInput (clearing its boxes) after a wrong code.
  const [attempt, setAttempt] = useState(0);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    getMe()
      .then((user) => {
        setEmail(user.email || "");
        setPhase(user.email_verified ? "done" : "entry");
      })
      .catch(() => setPhase("entry")); // an expired session redirects to /login on its own
  }, []);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setInterval(() => setCooldown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [cooldown]);

  async function handleComplete(code) {
    setError(null);
    setNotice(null);
    setOtpError(false);
    setPhase("submitting");
    try {
      await verifyEmail(code);
      setPhase("done");
    } catch (err) {
      setError(err.message);
      setOtpError(true);
      setAttempt((n) => n + 1);
      setPhase("entry");
    }
  }

  async function handleResend() {
    setError(null);
    setNotice(null);
    try {
      await resendVerification();
      setNotice(`A new code is on its way to ${email || "your inbox"}.`);
      setCooldown(RESEND_COOLDOWN_SECONDS);
      setAttempt((n) => n + 1);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="w-full">
      <h1 className="mt-7.5 text-center font-display text-[clamp(30px,3.4vw,42px)] leading-[1.02] font-bold">
        {phase === "done" ? "Email confirmed" : "Check your inbox"}
      </h1>
      <p className="mt-3 text-center text-sm leading-[1.55] text-soft">
        {phase === "done"
          ? "Your address is verified and your account is protected."
          : `We sent a six-digit code to ${email || "your email address"}. It expires in 15 minutes.`}
      </p>

      {error && (
        <div role="alert" className="mt-6 border border-brand bg-brand-soft px-3.5 py-2.5 text-[13px] text-foreground">
          {error}
        </div>
      )}
      {notice && (
        <div role="status" className="mt-6 border border-panel-border bg-field px-3.5 py-2.5 text-[13px] text-foreground">
          {notice}
        </div>
      )}

      {(phase === "entry" || phase === "submitting") && (
        <div className="aura-step-enter mt-7 flex flex-col items-center gap-5">
          <OTPInput key={attempt} onComplete={handleComplete} error={otpError} disabled={phase === "submitting"} />
          <button
            type="button"
            onClick={handleResend}
            disabled={cooldown > 0 || phase === "submitting"}
            className="cursor-pointer text-[12.5px] font-semibold text-brand transition hover:underline disabled:cursor-not-allowed disabled:text-mute disabled:no-underline"
          >
            {cooldown > 0 ? `Resend code in ${cooldown}s` : "Send a new code"}
          </button>
        </div>
      )}

      {phase === "done" && (
        <div className="aura-step-enter mt-7">
          <button
            type="button"
            onClick={() => router.replace("/practice")}
            className="h-13 w-full cursor-pointer bg-foreground text-[11px] font-bold tracking-[0.2em] text-background uppercase transition hover:bg-brand hover:text-on-brand"
          >
            Start practising
          </button>
        </div>
      )}

      {phase !== "done" && (
        <p className="mt-7 text-center text-[13px] text-soft">
          <Link href="/practice" className="font-bold text-foreground underline underline-offset-[3px] transition hover:text-brand">
            Skip for now
          </Link>
          <span className="text-mute"> — you can verify later from your profile.</span>
        </p>
      )}
    </div>
  );
}
