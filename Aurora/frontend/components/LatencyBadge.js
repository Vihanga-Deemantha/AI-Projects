"use client";

/** Small stt/llm/total readout from the `done` message's `timings` object. */
export default function LatencyBadge({ timings }) {
  if (!timings) return null;
  const ttfs = timings.llm_ttfs_ms;

  return (
    <div className="flex flex-wrap items-center gap-3 border border-panel-border bg-panel px-4 py-2 text-[11px] text-soft">
      <span>STT {fmt(timings.stt_ms)}</span>
      <Dot />
      <span>LLM (1st sentence) {fmt(ttfs)}</span>
      <Dot />
      <span className="font-bold text-foreground">Total {fmt(timings.total_ms)}</span>
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
