"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import AppSidebar from "@/components/AppSidebar";
import { getSession } from "@/lib/api";
import { formatDate, formatDuration } from "../page";

export default function SessionDetailPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-1 flex-col lg:flex-row">
        <AppSidebar />
        <SessionDetail />
      </div>
    </AuthGuard>
  );
}

function SessionDetail() {
  const { id } = useParams();
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getSession(id)
      .then((d) => {
        if (cancelled) return;
        setSession(d);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
      <Link href="/history" className="flex items-center gap-2 text-sm font-semibold text-foreground/55 transition hover:text-brand">
        <BackIcon className="h-3.5 w-3.5" />
        Back to Speech History
      </Link>

      {status === "loading" && (
        <p className="mt-6 text-sm text-foreground/40">Loading session…</p>
      )}

      {status === "error" && (
        <div className="mt-6 rounded-xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-500">
          {error}
        </div>
      )}

      {status === "ready" && (
        <>
          <header className="mt-5 mb-7 flex flex-wrap items-center gap-5 rounded-[20px] border border-brand/20 bg-linear-to-br from-brand-soft to-transparent p-5 sm:p-6">
            <span className="h-14 w-14 shrink-0 rounded-2xl bg-[radial-gradient(circle_at_36%_30%,#b4a8ff,#8b7cff_34%,#5541c9_90%)] shadow-[0_0_22px_rgba(139,124,255,0.4)]" />
            <div className="min-w-40 flex-1">
              <h1 className="font-display text-xl font-bold capitalize">
                {session.scenario} · {session.style}
              </h1>
              <p className="mt-1 text-xs text-foreground/50">
                {session.style} · voice: {session.voice} · {formatDate(session.started_at)}
              </p>
            </div>
            <div className="flex gap-6">
              <HeaderStat value={session.turn_count} label="Turns" />
              <HeaderStat value={session.correction_count} label="Corrections" tone="rose" />
              <HeaderStat value={formatDuration(session.duration_seconds)} label="Duration" />
            </div>
          </header>

          {session.messages.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-panel-border p-8 text-center text-sm text-foreground/40">
              This session has no turns recorded.
            </p>
          ) : (
            <div className="flex flex-col gap-4">
              {session.messages.map((m) => (
                <Turn key={m.id} message={m} />
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}

function HeaderStat({ value, label, tone }) {
  return (
    <div className="text-center">
      <p className={`font-display text-lg font-bold ${tone === "rose" ? "text-rose-500" : ""}`}>{value}</p>
      <p className="text-[10px] uppercase tracking-wide text-foreground/40">{label}</p>
    </div>
  );
}

function Turn({ message }) {
  const isUser = message.role === "user";
  return (
    <div className={isUser ? "self-end text-right" : "self-start"}>
      <div
        className={`inline-block max-w-xl rounded-2xl border px-4 py-2.5 text-left text-sm ${
          isUser
            ? "rounded-br-sm border-brand bg-linear-to-br from-brand to-brand-dark text-white"
            : "rounded-bl-sm border-brand/20 bg-brand-soft text-foreground"
        }`}
      >
        <p className={`mb-1 text-[10px] font-semibold uppercase tracking-wide ${isUser ? "text-white/60" : "text-brand"}`}>
          {isUser ? "You" : "AURA"}
        </p>
        <p>{message.content}</p>
      </div>

      {message.corrections.length > 0 && (
        <div className="mt-2 flex flex-col gap-2 text-left">
          {message.corrections.map((c) => (
            <CorrectionCard key={c.id} correction={c} />
          ))}
        </div>
      )}
    </div>
  );
}

function CorrectionCard({ correction }) {
  const isError = correction.is_error;
  return (
    <div
      className={`max-w-xl rounded-xl border p-3 text-sm ${
        isError ? "border-rose-500/25 bg-rose-500/10" : "border-sky-500/25 bg-sky-500/10"
      }`}
    >
      <p className={`mb-1 text-xs font-semibold uppercase tracking-wide ${isError ? "text-rose-500" : "text-sky-500"}`}>
        {correction.category} · {correction.subtype.replaceAll("_", " ")}
      </p>
      <p className="text-foreground/70">
        <span className="line-through decoration-rose-400/60">{correction.original}</span>
        {" → "}
        <span className="font-medium text-foreground">{correction.correction}</span>
      </p>
      <p className="mt-1 text-xs text-foreground/50">{correction.explanation}</p>
    </div>
  );
}

function BackIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" {...props}>
      <path d="M15 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
