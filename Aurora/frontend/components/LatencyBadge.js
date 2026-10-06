"use client";

import { useState } from "react";

/**
 * How long the last turn took, from the `done` message's `timings` object. It leads with time-to-first-audio,
 * the wait the learner actually feels, and keeps the breakdown (speech-to-text, the language model's first
 * sentence, the total) one click away: it is engineering detail that most learners do not need on screen.
 */
export default function LatencyBadge({ timings }) {
  const [open, setOpen] = useState(false);
  if (!timings) return null;
  const firstAudio = timings.first_audio_ms;

  return (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border border-panel-border bg-panel px-4 py-2 text-xs text-soft">
      <span className="font-bold text-foreground">
        {firstAudio != null ? `First audio ${seconds(firstAudio)}` : `Turn took ${seconds(timings.total_ms)}`}
      </span>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="cursor-pointer underline underline-offset-[3px] transition hover:text-brand"
      >
        {open ? "Hide details" : "Details"}
      </button>
      {open && (
        <>
          <span>Speech-to-text {ms(timings.stt_ms)}</span>
          <Dot />
          <span>First sentence written {ms(timings.llm_ttfs_ms)}</span>
          <Dot />
          <span>Whole turn {ms(timings.total_ms)}</span>
        </>
      )}
    </div>
  );
}

function seconds(value) {
  return value == null ? "—" : `${(value / 1000).toFixed(1)}s`;
}

function ms(value) {
  return value == null ? "—" : `${Math.round(value)}ms`;
}

function Dot() {
  return <span className="h-1 w-1 bg-mute" aria-hidden="true" />;
}
