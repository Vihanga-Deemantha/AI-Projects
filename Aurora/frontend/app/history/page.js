"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import AppSidebar from "@/components/AppSidebar";
import { getSessions } from "@/lib/api";

const PAGE_SIZE = 20;

export default function HistoryPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-1">
        <AppSidebar />
        <SessionList />
      </div>
    </AuthGuard>
  );
}

function SessionList() {
  const [data, setData] = useState(null);
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- resetting to the loading state before an async fetch, not deriving state from props
    setStatus("loading");
    getSessions({ limit: PAGE_SIZE, offset })
      .then((d) => {
        if (cancelled) return;
        setData(d);
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
  }, [offset]);

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-10 py-9">
      <header className="mb-7">
        <h1 className="font-display text-[28px] font-bold">Speech History</h1>
        <p className="text-sm text-foreground/50">
          Every past session, with the feedback you received.
        </p>
      </header>

      {status === "loading" && <p className="text-sm text-foreground/40">Loading sessions…</p>}

      {status === "error" && (
        <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-500">
          {error}
        </div>
      )}

      {status === "ready" && data.sessions.length === 0 && (
        <div className="rounded-2xl border border-dashed border-panel-border p-10 text-center">
          <p className="text-sm text-foreground/50">You haven&apos;t practised yet.</p>
          <Link
            href="/practice"
            className="mt-4 inline-block rounded-full bg-linear-to-br from-brand to-brand-dark px-6 py-3 font-display text-sm font-bold text-white shadow-lg shadow-brand/25 transition hover:brightness-110"
          >
            Start your first session
          </Link>
        </div>
      )}

      {status === "ready" && data.sessions.length > 0 && (
        <>
          <ul className="flex flex-col gap-3">
            {data.sessions.map((s) => (
              <li key={s.id}>
                <Link
                  href={`/history/${s.id}`}
                  className="flex flex-wrap items-center gap-5 rounded-2xl border border-panel-border bg-panel p-4.5 transition hover:border-brand/35"
                >
                  <span className="h-12 w-12 shrink-0 rounded-[14px] bg-[radial-gradient(circle_at_36%_30%,#b4a8ff,#8b7cff_34%,#5541c9_90%)] shadow-[0_0_18px_rgba(139,124,255,0.35)]" />
                  <div className="min-w-40 flex-1">
                    <p className="font-semibold capitalize">
                      {s.scenario} · {s.style}
                    </p>
                    <p className="mt-0.5 text-xs text-foreground/45">
                      {formatDate(s.started_at)} · voice: {s.voice}
                      {s.is_complete ? "" : " · unfinished"}
                    </p>
                  </div>
                  <div className="flex items-center gap-6 text-sm">
                    <Stat value={s.turn_count} label="turns" />
                    <Stat value={s.correction_count} label="corrections" tone="rose" />
                    <Stat value={formatDuration(s.duration_seconds)} label="duration" />
                  </div>
                  <ChevronIcon className="ml-1 h-4 w-4 text-foreground/25" />
                </Link>
              </li>
            ))}
          </ul>

          {data.total > PAGE_SIZE && (
            <div className="mt-6 flex items-center justify-between text-sm">
              <button
                type="button"
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}
                className="rounded-full border border-panel-border px-5 py-2.5 transition hover:border-brand/40 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>
              <span className="text-foreground/45">
                {offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}
              </span>
              <button
                type="button"
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= data.total}
                className="rounded-full border border-brand/35 px-5 py-2.5 font-semibold text-brand transition hover:bg-brand-soft disabled:cursor-not-allowed disabled:border-panel-border disabled:font-normal disabled:text-foreground disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </main>
  );
}

function Stat({ value, label, tone }) {
  return (
    <div className="text-center">
      <p className={`font-display font-bold ${tone === "rose" ? "text-rose-500" : ""}`}>{value}</p>
      <p className="text-[10px] uppercase tracking-wide text-foreground/40">{label}</p>
    </div>
  );
}

function ChevronIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function formatDate(iso) {
  return new Date(iso).toLocaleString([], {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function formatDuration(seconds) {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}
