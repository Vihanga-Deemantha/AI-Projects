"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import AppSidebar from "@/components/AppSidebar";
import { getSessions } from "@/lib/api";
import { faceSrc, getCompanion, sceneLabel, styleLabel } from "@/lib/characters";

const PAGE_SIZE = 20;

export default function HistoryPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-1 flex-col lg:flex-row">
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

  const sessions = data?.sessions ?? [];
  const partial = data && data.total > PAGE_SIZE ? " (this page)" : "";
  const sum = (key) => sessions.reduce((n, s) => n + (s[key] || 0), 0);

  return (
    <main className="min-w-0 flex-1 px-5 py-7 sm:px-8 lg:px-10 lg:pt-9 lg:pb-14">
      <header>
        <div className="text-[10px] font-bold tracking-[0.22em] text-soft uppercase">Archive</div>
        <h1 className="mt-2.5 font-display text-[clamp(30px,3.6vw,46px)] leading-none font-bold">Speech history</h1>
        <p className="mt-3 max-w-[38em] text-[15px] leading-[1.6] text-soft">
          Every past session, with the feedback you received. The mistakes you stop making are the measure.
        </p>
      </header>

      {status === "loading" && <p className="mt-6.5 text-sm text-mute">Loading sessions…</p>}

      {status === "error" && (
        <div role="alert" className="mt-6.5 border border-brand bg-brand-soft px-4 py-3 text-sm">{error}</div>
      )}

      {status === "ready" && sessions.length === 0 && (
        <div className="mt-6.5 border border-dashed border-panel-border p-10 text-center">
          <p className="text-sm text-soft">You haven&apos;t practised yet.</p>
          <Link
            href="/practice"
            className="mt-4 inline-flex h-12 items-center bg-foreground px-6.5 text-[11px] font-bold tracking-[0.18em] text-background uppercase transition hover:bg-brand hover:text-on-brand"
          >
            Start your first session
          </Link>
        </div>
      )}

      {status === "ready" && sessions.length > 0 && (
        <>
          <div className="mt-6.5 flex flex-wrap">
            <StatCard value={data.total} label="Sessions" />
            <StatCard value={sum("turn_count")} label={`Turns${partial}`} />
            <StatCard value={sum("correction_count")} label={`Corrections${partial}`} />
            <StatCard value={formatDuration(sum("duration_seconds"))} label={`Time spoken${partial}`} />
          </div>

          <ul className="mt-5.5 flex flex-col border border-panel-border bg-panel">
            {sessions.map((s) => {
              const who = getCompanion(s.voice);
              return (
                <li key={s.id} className="border-b border-panel-border last:border-b-0">
                  <Link
                    href={`/history/${s.id}`}
                    className="flex flex-wrap items-center gap-4 px-5 py-4 transition hover:bg-brand-soft/60"
                  >
                    <span
                      role="img"
                      aria-label={who.name}
                      className="h-11.5 w-11.5 flex-none rounded-full bg-brand-soft bg-cover bg-top"
                      style={{ backgroundImage: `url('${faceSrc(who.id, "neutral")}')` }}
                    />
                    <div className="min-w-0 flex-[1_1_180px]">
                      <div className="text-[15px] font-bold">
                        {sceneLabel(s.scenario)} · {styleLabel(s.style)}
                      </div>
                      <div className="mt-1 text-xs text-mute">
                        {formatDate(s.started_at)} · with {who.name}
                        {s.is_complete ? "" : " · unfinished"}
                      </div>
                    </div>
                    <Figure value={s.turn_count} label="Turns" className="min-w-15.5" />
                    <Figure value={s.correction_count} label="Fixes" className="min-w-15.5" accent />
                    <Figure value={formatDuration(s.duration_seconds)} label="Length" className="min-w-18" />
                    <span className="text-[15px] text-mute" aria-hidden="true">&rarr;</span>
                  </Link>
                </li>
              );
            })}
          </ul>

          {data.total > PAGE_SIZE && (
            <div className="mt-6 flex items-center justify-between text-sm">
              <button
                type="button"
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}
                className="h-11 cursor-pointer border border-panel-border px-5 text-[11px] font-bold tracking-[0.16em] uppercase transition hover:border-brand hover:text-brand disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>
              <span className="text-mute">
                {offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}
              </span>
              <button
                type="button"
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= data.total}
                className="h-11 cursor-pointer border border-brand px-5 text-[11px] font-bold tracking-[0.16em] text-brand uppercase transition hover:bg-brand hover:text-on-brand disabled:cursor-not-allowed disabled:border-panel-border disabled:text-foreground disabled:opacity-40"
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

function StatCard({ value, label }) {
  return (
    <div className="-mr-px -mb-px flex-[1_1_150px] border border-panel-border bg-panel p-5">
      <div className="font-display text-[32px] leading-none">{value}</div>
      <div className="mt-2 text-[9.5px] font-bold tracking-[0.16em] text-soft uppercase">{label}</div>
    </div>
  );
}

function Figure({ value, label, accent, className = "" }) {
  return (
    <div className={`text-center ${className}`}>
      <div className={`font-display text-lg font-bold ${accent ? "text-brand" : ""}`}>{value}</div>
      <div className="mt-0.75 text-[9px] font-bold tracking-[0.14em] text-mute uppercase">{label}</div>
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
