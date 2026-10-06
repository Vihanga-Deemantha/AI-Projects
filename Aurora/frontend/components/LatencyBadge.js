"use client";

/**
 * Small latency readout from the `done` message's `timings` object. Leads with
 * time-to-first-audio — what the learner actually waits for — then the pieces.
 */
export default function LatencyBadge({ timings }) {
  if (!timings) return null;
  const firstAudio = timings.first_audio_ms;

  return (
    <div className="flex flex-wrap items-center gap-3 border border-panel-border bg-panel px-4 py-2 text-[11px] text-soft">
      <span>STT {fmt(timings.stt_ms)}</span>
      <Dot />
      <span>LLM (1st sentence) {fmt(timings.llm_ttfs_ms)}</span>
      <Dot />
      {firstAudio != null && (
        <>
          <span className="font-bold text-foreground">First audio {fmt(firstAudio)}</span>
          <Dot />
        </>
      )}
      <span>Total {fmt(timings.total_ms)}</span>
    </div>
  );
}

function fmt(ms) {
  if (ms === undefined || ms === null) return "—";
  return `${Math.round(ms)}ms`;
}

function Dot() {
  return <span className="h-1 w-1 bg-mute" />;
}
