"use client";

/**
 * Session lifecycle cluster for the page header: a status chip that's always
 * visible (so it's never ambiguous what state you're in) plus Start / Pause /
 * End.
 *
 * "Start session" is a convenience — holding the mic also starts a session
 * automatically with whatever companion/style/scenario is currently
 * selected, so this button is optional, not a gate.
 */
export default function SessionControls({ phase, starting, canPause, onStart, onTogglePause, onEnd }) {
  const badge = PHASE_BADGE[phase] ?? PHASE_BADGE.idle;

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <span className="inline-flex h-10 items-center gap-2 border border-panel-border px-4 text-[10px] font-bold tracking-[0.16em] whitespace-nowrap text-soft uppercase">
        <span className={`h-1.75 w-1.75 ${badge.live ? "aura-blink bg-brand" : "bg-mute"}`} />
        {badge.label}
      </span>

      {phase === "idle" ? (
        <button
          type="button"
          onClick={onStart}
          disabled={starting}
          className="h-10 cursor-pointer bg-foreground px-4.5 text-[10px] font-bold tracking-[0.16em] whitespace-nowrap text-background uppercase transition hover:bg-brand hover:text-on-brand disabled:cursor-not-allowed disabled:opacity-50"
        >
          {starting ? "Starting…" : "Start session"}
        </button>
      ) : (
        <>
          <button
            type="button"
            onClick={onTogglePause}
            disabled={!canPause}
            title={canPause ? undefined : "Nothing to pause right now — your companion isn't speaking"}
            className="h-10 cursor-pointer border border-panel-border px-4.5 text-[10px] font-bold tracking-[0.16em] whitespace-nowrap text-soft uppercase transition hover:border-brand hover:text-brand disabled:cursor-not-allowed disabled:opacity-40"
          >
            {phase === "paused" ? "Resume" : "Pause"}
          </button>
          <button
            type="button"
            onClick={onEnd}
            className="h-10 cursor-pointer border border-panel-border px-4.5 text-[10px] font-bold tracking-[0.16em] whitespace-nowrap text-soft uppercase transition hover:border-brand hover:text-brand"
          >
            End session
          </button>
        </>
      )}
    </div>
  );
}

const PHASE_BADGE = {
  idle: { label: "Not started", live: false },
  active: { label: "Ready", live: false },
  recording: { label: "Listening", live: true },
  thinking: { label: "Thinking", live: true },
  speaking: { label: "Speaking", live: true },
  paused: { label: "Paused", live: false },
};
