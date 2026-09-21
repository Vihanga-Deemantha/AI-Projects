"use client";

import { useEffect } from "react";
import { getCompanion, preload, spriteSrc } from "@/lib/characters";
import { useTicker } from "@/hooks/motion";
import { SpriteCrossfade } from "@/components/Sprite";
import Waveform from "./Waveform";
import RecordButton from "./RecordButton";

const MOUTH_MS = 420;
const POSES = ["idle", "listening", "thinking", "talking_open", "talking_emphatic"];

/**
 * The practice stage: the selected companion stands in a tinted panel and
 * changes pose with the conversation — listening while you hold the mic,
 * thinking while a reply is generated, talking (mouth alternating between
 * two poses) while the reply plays, idle otherwise. Underneath, the real
 * analyser-driven Waveform reacts to the live mic or TTS playback, followed
 * by the hold-to-speak bar.
 *
 * `micAnalyser` is lifted up to the parent (rather than owned locally) so
 * the session status chip can show "Listening" in sync with this stage.
 */
export default function WaveformHero({
  companionId,
  recordDisabled,
  isProcessing,
  isPlaying,
  paused,
  playbackAnalyser,
  micAnalyser,
  onAnalyser,
  onRecordingComplete,
}) {
  const companion = getCompanion(companionId);
  const speaking = isPlaying && !paused;
  const activeAnalyser = micAnalyser || (speaking ? playbackAnalyser : null);

  // Alternate the two talking poses while the reply plays, so the figure
  // reads as speaking rather than holding one pose.
  const [mouth] = useTicker(MOUTH_MS, speaking);

  // Decode this companion's poses ahead of time so a pose change never waits
  // on the network mid-dissolve.
  useEffect(() => {
    preload(POSES.map((p) => spriteSrc(companion.id, p)));
  }, [companion.id]);

  let pose = "idle";
  let status = "Hold the mic to begin";
  if (micAnalyser) { pose = "listening"; status = "Listening…"; }
  else if (isProcessing) { pose = "thinking"; status = `${companion.name} is thinking…`; }
  else if (paused) { status = "Paused"; }
  else if (speaking) { pose = mouth % 2 === 0 ? "talking_open" : "talking_emphatic"; status = `${companion.name} is speaking…`; }

  const live = Boolean(micAnalyser) || isProcessing || speaking;

  return (
    <div className="flex flex-col gap-4.5">
      <div className="relative grid min-h-90 place-items-end justify-center overflow-hidden border border-panel-border bg-brand-soft px-6 sm:min-h-97.5">
        <div className="absolute top-[8%] left-1/2 aspect-square w-[74%] -translate-x-1/2 rounded-full bg-panel opacity-55" />
        <div className="absolute inset-x-0 bottom-0 h-[16%] bg-brand opacity-[0.16]" />

        <div className="absolute top-4 right-4 left-4 z-4 flex items-center gap-2 text-[10px] font-bold tracking-[0.16em] text-soft uppercase">
          <span className={`h-1.75 w-1.75 flex-none ${live ? "aura-blink bg-brand" : "bg-mute"}`} />
          <span className="truncate">{status}</span>
        </div>

        <div className={`relative z-3 -mb-0.5 h-75 max-w-full ${live ? "" : "aura-float"}`} style={{ aspectRatio: "700 / 680" }}>
          <div className="absolute bottom-[-1%] left-[10%] h-3.75 w-[80%] rounded-full bg-foreground opacity-[0.16] blur-[9px]" />
          <SpriteCrossfade
            src={spriteSrc(companion.id, pose)}
            alt={`${companion.name}, ${pose.replace(/_/g, " ")}`}
            className="absolute inset-0"
          />
        </div>

        <div className="absolute bottom-4.5 left-1/2 z-4 h-9 w-[min(240px,70%)] -translate-x-1/2">
          <Waveform analyser={activeAnalyser} barCount={24} className={micAnalyser ? "text-brand" : "text-foreground"} />
        </div>
      </div>

      <RecordButton
        disabled={recordDisabled || isProcessing}
        onAnalyser={onAnalyser}
        onRecordingComplete={onRecordingComplete}
      />
    </div>
  );
}
