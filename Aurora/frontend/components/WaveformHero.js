"use client";

import Waveform from "./Waveform";
import RecordButton from "./RecordButton";

/**
 * The "Live Voice Output" hero: a waveform with the push-to-talk mic
 * centered in it. The same Waveform component reacts to whichever
 * AnalyserNode is live — the mic while recording (red), or the TTS
 * playback queue while AURA replies (indigo).
 *
 * `micAnalyser` is lifted up to the parent (rather than owned locally) so
 * the session status bar can show "Listening…" in sync with this waveform.
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

  return (
    <div className="flex flex-col items-center gap-4 rounded-2xl border border-panel-border bg-panel p-6">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground/60">
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

      <div className="relative flex h-40 w-full items-center justify-center">
        {/* pointer-events-none is load-bearing: without it this absolutely
            positioned canvas sits in front of the RecordButton in the paint
            order and silently swallows every click/press meant for it. */}
        <div className="pointer-events-none absolute inset-0">
          <Waveform analyser={activeAnalyser} color={micAnalyser ? "#f43f5e" : "#6366f1"} />
        </div>
        <RecordButton
          disabled={recordDisabled || isProcessing}
          onAnalyser={onAnalyser}
          onRecordingComplete={onRecordingComplete}
        />
      </div>
    </div>
  );
}
