"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import NavBar from "@/components/NavBar";
import { getSessions } from "@/lib/api";

const PAGE_SIZE = 20;

export default function HistoryPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-1 flex-col">
        <NavBar />
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
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">Speech History</h1>
        <p className="text-sm text-foreground/50">
          Every past session, with the feedback you received.
        </p>
      </header>

      {status === "loading" && <p className="text-sm text-foreground/40">Loading sessions…</p>}

      {status === "error" && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {status === "ready" && data.sessions.length === 0 && (
        <div className="rounded-2xl border border-dashed border-panel-border p-10 text-center">
          <p className="text-sm text-foreground/50">You haven&apos;t practised yet.</p>
          <Link
            href="/practice"
            className="mt-4 inline-block rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-dark"
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
                  className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-panel-border bg-panel p-4 transition hover:border-brand/40"
                >
                  <div>
                    <p className="font-semibold capitalize">
                      {s.scenario} · {s.style}
                    </p>
                    <p className="text-xs text-foreground/45">
                      {formatDate(s.started_at)} · voice: {s.voice}
                      {s.is_complete ? "" : " · unfinished"}
                    </p>
                  </div>
                  <div className="flex items-center gap-5 text-sm">
                    <Stat value={s.turn_count} label="turns" />
                    <Stat value={s.correction_count} label="corrections" />
                    <Stat value={formatDuration(s.duration_seconds)} label="duration" />
                  </div>
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
                className="rounded-xl border border-panel-border px-4 py-2 transition hover:border-brand/40 disabled:cursor-not-allowed disabled:opacity-40"
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
                className="rounded-xl border border-panel-border px-4 py-2 transition hover:border-brand/40 disabled:cursor-not-allowed disabled:opacity-40"
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

function Stat({ value, label }) {
  return (
    <div className="text-center">
      <p className="font-semibold">{value}</p>
      <p className="text-[10px] uppercase tracking-wide text-foreground/40">{label}</p>
    </div>
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
