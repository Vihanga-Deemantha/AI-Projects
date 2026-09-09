"use client";

export default function Sidebar({ onNewSession, sessionActive }) {
  return (
    <aside className="flex w-64 shrink-0 flex-col gap-8 border-r border-panel-border bg-panel/60 px-6 py-8">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand text-white shadow-md shadow-indigo-200">
          <SpeakerWaveIcon className="h-6 w-6" />
        </div>
        <div>
          <p className="text-lg font-bold leading-tight">AURA</p>
          <p className="text-xs text-foreground/50">AI Speaking Coach</p>
        </div>
      </div>

      <nav className="flex flex-col gap-1">
        <NavItem icon={<ChatIcon />} label="Session" active />
        <NavItem icon={<HistoryIcon />} label="Conversations" disabled note="Phase 7" />
        <NavItem icon={<ChartIcon />} label="Progress" disabled note="Phase 8" />
      </nav>

      <button
        type="button"
        onClick={onNewSession}
        disabled={!sessionActive}
        className="mt-auto rounded-xl border border-panel-border bg-white px-4 py-2.5 text-sm font-medium text-foreground/80 shadow-sm transition hover:border-brand/40 hover:text-brand disabled:cursor-not-allowed disabled:opacity-40"
      >
        {sessionActive ? "End Session" : "No active session"}
      </button>
    </aside>
  );
}

function NavItem({ icon, label, active, disabled, note }) {
  return (
    <div
      className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium ${
        active
          ? "bg-brand/10 text-brand"
          : disabled
            ? "cursor-not-allowed text-foreground/30"
            : "text-foreground/70"
      }`}
    >
      <span className="h-5 w-5">{icon}</span>
      <span className="flex-1">{label}</span>
      {note && <span className="text-[10px] uppercase tracking-wide text-foreground/30">{note}</span>}
    </div>
  );
}

function SpeakerWaveIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M4 9v6h4l5 5V4L8 9H4Z" strokeLinejoin="round" />
      <path d="M16.5 8.5a5 5 0 0 1 0 7M19.5 5.5a9 9 0 0 1 0 13" strokeLinecap="round" />
    </svg>
  );
}
function ChatIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M21 12a8 8 0 1 1-3.2-6.4L21 4l-1 4.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function HistoryIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M3 12a9 9 0 1 0 9-9 9 9 0 0 0-9 9Z" />
      <path d="M12 7v5l3 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function ChartIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M4 20V10M12 20V4M20 20v-7" strokeLinecap="round" />
    </svg>
  );
}
