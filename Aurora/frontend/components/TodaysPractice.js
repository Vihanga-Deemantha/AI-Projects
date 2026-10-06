"use client";

/**
 * "Today's practice": the learner's top live weakness, with one click to start a
 * session that steers the conversation toward it (the coach does it silently —
 * no quiz, no lecture). Shows read-only while a session is running.
 *
 * `exercise` is GET /api/practice/today's `exercise`; `focus` is the focus id
 * currently selected for the next session (or null).
 */
export default function TodaysPractice({ exercise, focus, label, sessionActive, onAccept, onClear }) {
  if (!exercise) return null;
  const hasRealFocus = Boolean(exercise.focus);
  const active = Boolean(focus);

  return (
    <div className={`border p-5 ${active ? "border-brand bg-brand-soft" : "border-panel-border bg-panel"}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-[10px] font-bold tracking-[0.2em] text-brand uppercase">Today&apos;s practice</span>
        {active && (
          <span className="text-[10px] font-bold tracking-[0.14em] text-soft uppercase">
            {sessionActive ? "Focus for this session" : "Focus selected"}
          </span>
        )}
      </div>

      {active ? (
        <>
          <div className="mt-3 font-display text-[22px] leading-tight font-bold">{label}</div>
          <p className="mt-2 text-[12.5px] leading-normal text-soft">
            Your coach will steer the conversation so you get natural practice at this — without announcing it.
          </p>
          {!sessionActive && (
            <button type="button" onClick={onClear} className="mt-3.5 cursor-pointer text-[11px] font-bold tracking-[0.14em] text-soft uppercase underline underline-offset-[3px] transition hover:text-brand">
              Clear focus
            </button>
          )}
        </>
      ) : (
        <>
          <div className="mt-3 font-display text-[22px] leading-tight font-bold">{exercise.label}</div>
          <p className="mt-2 text-[12.5px] leading-normal text-soft">{exercise.why}</p>
          {hasRealFocus && !sessionActive && (
            <button
              type="button"
              onClick={() => onAccept(exercise)}
              className="mt-3.5 h-10 cursor-pointer bg-foreground px-4.5 text-[10px] font-bold tracking-[0.16em] whitespace-nowrap text-background uppercase transition hover:bg-brand hover:text-on-brand"
            >
              Practise this &rarr;
            </button>
          )}
        </>
      )}
    </div>
  );
}
