"use client";

/** 3 metric cards for the *current* session (not lifetime stats). */
export default function StatsRow({ turns, sessionSeconds, correctionsCount }) {
  return (
    <div className="flex flex-wrap">
      <StatCard value={turns} label="Turns" />
      <StatCard value={formatDuration(sessionSeconds)} label="Elapsed" />
      <StatCard value={correctionsCount} label="Corrections" />
    </div>
  );
}

function StatCard({ value, label }) {
  return (
    <div className="-mr-px -mb-px flex-[1_1_90px] border border-panel-border bg-panel p-4">
      <div className="font-display text-[26px] leading-none">{value}</div>
      <div className="mt-1.5 text-[9.5px] font-bold tracking-[0.16em] text-soft uppercase">{label}</div>
    </div>
  );
}

export function formatDuration(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds || 0));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}
