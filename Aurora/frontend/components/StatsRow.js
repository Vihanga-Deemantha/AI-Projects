"use client";

/** 3 metric cards for the *current* session (not lifetime stats — that's Phase 8). */
export default function StatsRow({ turns, sessionSeconds, correctionsCount }) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <StatCard icon={<TurnsIcon />} value={turns} label="Turns" tone="indigo" />
      <StatCard icon={<ClockIcon />} value={formatDuration(sessionSeconds)} label="Session Time" tone="violet" />
      <StatCard icon={<FlagIcon />} value={correctionsCount} label="Corrections Flagged" tone="rose" />
    </div>
  );
}

function StatCard({ icon, value, label, tone }) {
  const toneClasses = {
    indigo: "bg-indigo-50 text-indigo-600",
    violet: "bg-violet-50 text-violet-600",
    rose: "bg-rose-50 text-rose-600",
  }[tone];

  return (
    <div className="flex items-center gap-3 rounded-2xl border border-panel-border bg-panel p-4">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${toneClasses}`}>
        {icon}
      </div>
      <div>
        <p className="text-xl font-bold leading-tight">{value}</p>
        <p className="text-xs text-foreground/50">{label}</p>
      </div>
    </div>
  );
}

function formatDuration(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds || 0));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

function TurnsIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M4 6h16M4 12h10M4 18h16" strokeLinecap="round" />
    </svg>
  );
}
function ClockIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4l3 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function FlagIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M6 4v16" strokeLinecap="round" />
      <path d="M6 4h11l-2.5 3.5L17 11H6" strokeLinejoin="round" />
    </svg>
  );
}
