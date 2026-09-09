"use client";

/**
 * Explicit session lifecycle controls: Start / Pause / End, with a status
 * badge that's always visible so it's never ambiguous what state you're in.
 *
 * "Start Session" here is a convenience — holding the mic also starts a
 * session automatically with whatever voice/style/scenario is currently
 * selected, so this button is optional, not a gate.
 */
export default function SessionControls({ phase, starting, canPause, onStart, onTogglePause, onEnd }) {
  const badge = PHASE_BADGE[phase] ?? PHASE_BADGE.idle;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-panel-border bg-panel px-5 py-3">
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${badge.dot}`} />
        <span className={`text-sm font-semibold ${badge.text}`}>{badge.label}</span>
      </div>

      <div className="flex items-center gap-2">
        {phase === "idle" ? (
          <button
            type="button"
            onClick={onStart}
            disabled={starting}
            className="rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-50"
          >
            {starting ? "Starting…" : "Start Session"}
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={onTogglePause}
              disabled={!canPause}
              title={canPause ? undefined : "Nothing to pause right now — AURA isn't speaking"}
              className="rounded-xl border border-panel-border px-4 py-2 text-sm font-medium text-foreground/70 transition hover:border-brand/40 hover:text-brand disabled:cursor-not-allowed disabled:opacity-40"
            >
              {phase === "paused" ? "Resume" : "Pause"}
            </button>
            <button
              type="button"
              onClick={onEnd}
              className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-medium text-rose-600 transition hover:bg-rose-100"
            >
              End Session
            </button>
          </>
        )}
      </div>
    </div>
  );
}

const PHASE_BADGE = {
  idle: { label: "Not started", dot: "bg-foreground/20", text: "text-foreground/50" },
  active: { label: "Session active — ready", dot: "bg-emerald-500", text: "text-emerald-600" },
  recording: { label: "Listening…", dot: "animate-pulse bg-rose-500", text: "text-rose-600" },
  thinking: { label: "AURA is thinking…", dot: "animate-pulse bg-amber-500", text: "text-amber-600" },
  speaking: { label: "AURA is speaking…", dot: "animate-pulse bg-emerald-500", text: "text-emerald-600" },
  paused: { label: "Paused", dot: "bg-amber-500", text: "text-amber-600" },
};
