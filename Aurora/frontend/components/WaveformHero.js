"use client";

import Waveform from "./Waveform";
import RecordButton from "./RecordButton";

/**
 * The push-to-talk orb + soundwave. Unlike the earlier version, the orb and
 * the soundwave strip are separate, non-overlapping blocks (stacked
 * vertically) rather than the waveform sitting full-bleed behind the button
 * — so there's no pointer-events trap between them anymore.
 *
 * The same Waveform component reacts to whichever AnalyserNode is live —
 * the mic while recording (rose), or the TTS playback queue while AURA
 * replies (violet/brand).
 *
 * `micAnalyser` is lifted up to the parent (rather than owned locally) so
 * the session status bar can show "Listening…" in sync with this hero.
 */
export default function WaveformHero({
  recordDisabled,
  isProcessing,
  isPlaying,
  paused,
  playbackAnalyser,
  micAnalyser,
  onAnalyser,
  onRecordingComplete,
}) {
  const activeAnalyser = micAnalyser || (isPlaying && !paused ? playbackAnalyser : null);

  let statusLabel = "Hold the mic to talk — this starts your session automatically";
  if (micAnalyser) statusLabel = "Listening…";
  else if (isProcessing) statusLabel = "AURA is thinking…";
  else if (paused) statusLabel = "Paused";
  else if (isPlaying) statusLabel = "AURA is speaking…";

  const colorTop = micAnalyser ? "#ffd0da" : "#c3b8ff";
  const colorBottom = micAnalyser ? "#fb7185" : "#7a68e8";

  return (
    <div className="relative flex flex-col items-center gap-5 overflow-hidden rounded-2xl border border-panel-border bg-panel/60 p-6">
      <div className="pointer-events-none absolute -top-24 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-brand/15 blur-3xl" />

      <div className="relative flex items-center gap-2 text-sm font-medium text-foreground/60">
        <span
          className={`h-2.5 w-2.5 rounded-full ${
            micAnalyser
              ? "animate-pulse bg-rose-500"
              : activeAnalyser
                ? "animate-pulse bg-emerald-500"
                : "bg-foreground/20"
          }`}
        />
        {statusLabel}
      </div>

      <div className="relative flex h-33 w-33 items-center justify-center">
        <div className="aura-ring-spin pointer-events-none absolute -inset-3.5 rounded-full bg-[conic-gradient(from_0deg,transparent,rgba(139,124,255,0.5),transparent_40%)]" />
        <RecordButton
          disabled={recordDisabled || isProcessing}
          onAnalyser={onAnalyser}
          onRecordingComplete={onRecordingComplete}
        />
      </div>

      <div className="relative h-10 w-full max-w-sm">
        <Waveform analyser={activeAnalyser} colorTop={colorTop} colorBottom={colorBottom} barCount={40} />
      </div>
    </div>
  );
}
