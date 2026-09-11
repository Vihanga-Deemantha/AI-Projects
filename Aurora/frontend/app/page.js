"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { isLoggedIn } from "@/lib/auth";
import Waveform from "@/components/Waveform";

export default function HomePage() {
  const [loggedIn, setLoggedIn] = useState(false);

  // After mount: localStorage is unavailable during SSR, so the page renders
  // logged-out first and adjusts once hydrated.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is client-only; reading it during render would mismatch SSR output
    setLoggedIn(isLoggedIn());
  }, []);

  return (
    <div className="flex min-h-screen flex-1 flex-col">
      <header className="flex items-center justify-between px-8 py-9 lg:px-16">
        <div className="flex items-center gap-3">
          <span className="flex h-9.5 w-9.5 items-center justify-center rounded-[11px] bg-linear-to-br from-brand to-brand-dark font-display text-sm font-bold text-white shadow-[0_0_20px_rgba(139,124,255,0.5)]">
            A
          </span>
          <span className="font-display text-2xl font-bold">AURA</span>
        </div>

        <nav className="hidden items-center gap-10 sm:flex">
          <a href="#how-it-works" className="text-sm font-medium text-foreground/55 transition hover:text-foreground">
            How it works
          </a>
          <a href="#styles" className="text-sm font-medium text-foreground/55 transition hover:text-foreground">
            Styles &amp; scenarios
          </a>
          {loggedIn && (
            <Link href="/history" className="text-sm font-medium text-foreground/55 transition hover:text-foreground">
              Speech history
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-2">
          {loggedIn ? (
            <Link
              href="/practice"
              className="rounded-full bg-linear-to-br from-brand to-brand-dark px-5 py-2.5 font-display text-sm font-bold text-white shadow-lg shadow-brand/25 transition hover:brightness-110"
            >
              Go to Practice
            </Link>
          ) : (
            <>
              <Link href="/login" className="rounded-full px-4 py-2.5 text-sm font-semibold text-foreground/70 transition hover:text-foreground">
                Log In
              </Link>
              <Link
                href="/signup"
                className="rounded-full bg-linear-to-br from-brand to-brand-dark px-5 py-2.5 font-display text-sm font-bold text-white shadow-lg shadow-brand/25 transition hover:brightness-110"
              >
                Sign Up
              </Link>
            </>
          )}
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center px-6 pt-10 pb-16 text-center sm:pt-16">
        <div className="mb-9 flex items-center gap-2 rounded-full border border-brand/30 bg-brand-soft px-4 py-2 text-xs font-bold tracking-wide text-brand">
          <SparkIcon className="h-3.5 w-3.5" />
          AN AI THAT ACTUALLY LISTENS
        </div>

        <h1 className="max-w-3xl text-balance font-display text-4xl leading-[1.08] font-bold tracking-tight sm:text-6xl">
          Speak naturally.
          <br />
          Get{" "}
          <span className="bg-linear-to-r from-brand to-sky-400 bg-clip-text italic text-transparent">
            smarter
          </span>{" "}
          feedback.
        </h1>
        <p className="mt-6 max-w-xl text-base text-foreground/60">
          Have a real spoken conversation with AURA, then see exactly where your
          grammar and vocabulary can improve — turn by turn, not a canned quiz.
        </p>

        <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
          <Link
            href={loggedIn ? "/practice" : "/signup"}
            className="rounded-full bg-linear-to-br from-brand to-brand-dark px-8 py-4 font-display text-[15px] font-bold text-white shadow-xl shadow-brand/30 transition hover:brightness-110"
          >
            {loggedIn ? "Start Practising" : "Start Speaking Free"}
          </Link>
          {!loggedIn && (
            <Link
              href="/login"
              className="rounded-full border border-panel-border bg-panel px-8 py-4 text-sm font-semibold text-foreground/70 transition hover:border-brand/40 hover:text-brand"
            >
              I already have an account
            </Link>
          )}
        </div>

        {/* Orb + idle soundwave — decorative here (no live audio), reusing
            the same Waveform canvas the practice screen drives with real
            AnalyserNode data, so the idle animation matches exactly. */}
        <div className="relative mt-16 flex h-75 w-75 items-center justify-center">
          <div className="aura-ring-spin absolute -inset-9 rounded-full bg-[conic-gradient(from_0deg,transparent,rgba(139,124,255,0.5),transparent_40%)] opacity-70" />
          <div className="absolute inset-4 rounded-full border border-brand/20" />
          <div className="aura-orb-breathe h-64 w-64 rounded-full bg-[radial-gradient(circle_at_38%_32%,#b4a8ff_0%,#8b7cff_32%,#5541c9_68%,#2c1f6b_100%)] shadow-[0_0_90px_rgba(139,124,255,0.5),0_0_200px_rgba(139,124,255,0.25)]" />
          <div className="absolute bottom-9 h-11 w-52">
            <Waveform analyser={null} barCount={32} />
          </div>
        </div>

        <div id="styles" className="mt-24 grid w-full gap-5 text-left sm:grid-cols-3">
          <Feature
            title="A real conversation"
            body="You talk, AURA replies out loud in under two seconds — not a chatbot with a play button bolted on."
          />
          <Feature
            title="Feedback that teaches"
            body="Grammar and vocabulary corrections after every turn, with the reason behind each one — not just a red mark."
          />
          <Feature
            title="Practise your way"
            body="4 voices, 6 English styles and 5 scenarios — from casual chat to a job interview."
          />
        </div>

        <div id="how-it-works" className="mt-20 w-full rounded-[28px] border border-brand/20 bg-linear-to-br from-brand-soft to-transparent p-10 text-left sm:p-14">
          <div className="grid gap-10 sm:grid-cols-3">
            <Step number="01" title="Press and talk" body="Hold the mic, pick a voice, style and scenario — or just start." />
            <Step number="02" title="AURA replies" body="A natural spoken reply, streamed sentence by sentence." />
            <Step number="03" title="See what to fix" body="Grammar and vocabulary notes land right after — and stay in your speech history." />
          </div>
        </div>

        <p className="mt-16 max-w-lg text-xs text-foreground/35">
          Conversational style presets are informed by regional English vocabulary
          and phrasing — not claims of accent reproduction.
        </p>
      </main>
    </div>
  );
}

function Feature({ title, body }) {
  return (
    <div className="rounded-2xl border border-panel-border bg-panel p-6">
      <h2 className="font-display text-lg font-bold">{title}</h2>
      <p className="mt-2 text-sm leading-relaxed text-foreground/55">{body}</p>
    </div>
  );
}

function Step({ number, title, body }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="font-display text-4xl font-bold text-brand/40">{number}</span>
      <h4 className="font-semibold">{title}</h4>
      <p className="text-sm leading-relaxed text-foreground/50">{body}</p>
    </div>
  );
}

function SparkIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" {...props}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4" strokeLinecap="round" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}
