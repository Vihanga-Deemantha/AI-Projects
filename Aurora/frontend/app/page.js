"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { isLoggedIn } from "@/lib/auth";

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
      <header className="flex items-center justify-between px-6 py-4 sm:px-10">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand font-bold text-white">
            A
          </span>
          <span className="font-bold">AURA</span>
        </div>
        <nav className="flex items-center gap-2">
          {loggedIn ? (
            <Link href="/practice" className="rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-dark">
              Go to Practice
            </Link>
          ) : (
            <>
              <Link href="/login" className="rounded-xl px-4 py-2 text-sm font-medium text-foreground/70 transition hover:text-brand">
                Log In
              </Link>
              <Link href="/signup" className="rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-dark">
                Sign Up
              </Link>
            </>
          )}
        </nav>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center px-6 py-16 text-center sm:py-24">
        <h1 className="max-w-3xl text-4xl font-bold leading-tight sm:text-5xl">
          Speak naturally.<br />Get smarter feedback.
        </h1>
        <p className="mt-5 max-w-xl text-base text-foreground/60">
          AURA is an AI speaking coach. Have a real spoken conversation, then see
          exactly where your grammar and vocabulary can improve — turn by turn.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            href={loggedIn ? "/practice" : "/signup"}
            className="rounded-xl bg-brand px-6 py-3 text-sm font-semibold text-white shadow-md shadow-indigo-200 transition hover:bg-brand-dark"
          >
            {loggedIn ? "Start Practising" : "Get Started Free"}
          </Link>
          {!loggedIn && (
            <Link
              href="/login"
              className="rounded-xl border border-panel-border bg-panel px-6 py-3 text-sm font-semibold text-foreground/70 transition hover:border-brand/40 hover:text-brand"
            >
              I already have an account
            </Link>
          )}
        </div>

        <div className="mt-20 grid w-full gap-5 text-left sm:grid-cols-3">
          <Feature
            title="Real conversation"
            body="Speak out loud and AURA replies in a natural voice — not a chatbot with a play button."
          />
          <Feature
            title="Feedback that teaches"
            body="Grammar and vocabulary corrections after each turn, with the reason behind every fix."
          />
          <Feature
            title="Practise your way"
            body="4 voices, 6 English styles and 5 scenarios — from casual chat to job interviews."
          />
        </div>

        <p className="mt-16 text-xs text-foreground/35">
          Conversational style presets are informed by regional English vocabulary
          and phrasing — not claims of accent reproduction.
        </p>
      </main>
    </div>
  );
}

function Feature({ title, body }) {
  return (
    <div className="rounded-2xl border border-panel-border bg-panel p-5">
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1.5 text-sm text-foreground/55">{body}</p>
    </div>
  );
}
