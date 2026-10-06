"use client";

import { useState } from "react";
import { playWord } from "@/lib/wordAudio";

/**
 * How the learner spoke on one turn, under their bubble: fluency score, speaking
 * rate, pauses, fillers, clarity — and the few words the recogniser was least
 * sure of, each with a button to hear it said (normally, or slowly).
 *
 * `fluency` and `clarity` are the objects the backend sends in the stream's
 * `metrics` event and in history (services/fluency.py, services/clarity.py).
 * `voice` is the companion whose voice says the words, and `style` the session's speaking style (the accent).
 */
export default function SpeechMetrics({ fluency, clarity, voice, style, detailed = false }) {
  if (!fluency && !clarity) return null;

  return (
    <div className="mt-1.5 flex flex-col items-end gap-1.5">
      <div className="flex flex-wrap justify-end gap-1.5">
        {fluency && <FluencyChips fluency={fluency} />}
        {clarity && (
          <Chip
            strong
            title={
              clarity.word_level
                ? "Clarity: how confidently speech recognition identified your words. An estimate — not phoneme-level pronunciation scoring."
                : "Clarity (rough): the recogniser in use gives no per-word confidence, so this is estimated from overall confidence only."
            }
          >
            Clarity {clarity.score}
            {!clarity.word_level && "*"}
          </Chip>
        )}
      </div>

      {detailed && fluency && <FluencyDetail fluency={fluency} />}
      <UnclearWords clarity={clarity} voice={voice} style={style} />
      {detailed && clarity && (
        <p className="max-w-[30em] text-right text-[11px] leading-normal text-mute">
          Clarity is an estimate from speech-recognition confidence, not phoneme-level pronunciation analysis.
        </p>
      )}
    </div>
  );
}

function FluencyChips({ fluency }) {
  const { score, wpm, pause_count, filler_count, filler_breakdown, repetition_count, hesitations_tracked } = fluency;
  const fillerList = fillerText(filler_breakdown);

  return (
    <>
      <Chip strong title="Fluency score out of 100: speaking rate, pauses, fillers and repetitions">
        Fluency {score}
      </Chip>
      {wpm != null && <Chip title="Words per minute while speaking">{Math.round(wpm)} wpm</Chip>}
      <Chip muted={pause_count === 0} title="Pauses in the middle of a thought (not the gaps between sentences)">
        {pause_count} {pause_count === 1 ? "pause" : "pauses"}
      </Chip>
      <Chip
        muted={filler_count === 0}
        title={
          hesitations_tracked
            ? fillerList || "No filler words detected"
            : `${fillerList || "None detected"} — "um" and "uh" can't be detected with the local speech recogniser (set STT_PROVIDER=groq on the server to count them)`
        }
      >
        {filler_count} {filler_count === 1 ? "filler" : "fillers"}
        {!hesitations_tracked && "*"}
      </Chip>
      {repetition_count > 0 && (
        <Chip title="A word repeated back to back">
          {repetition_count} repeat{repetition_count === 1 ? "" : "s"}
        </Chip>
      )}
    </>
  );
}

function FluencyDetail({ fluency }) {
  const fillerList = fillerText(fluency.filler_breakdown);
  if (!fillerList && !(fluency.longest_pause_seconds > 0) && fluency.hesitations_tracked) return null;
  return (
    <p className="max-w-[30em] text-right text-[11px] leading-normal text-mute">
      {fillerList && <>Fillers: {fillerList}. </>}
      {fluency.longest_pause_seconds > 0 && <>Longest pause {fluency.longest_pause_seconds.toFixed(1)}s. </>}
      {!fluency.hesitations_tracked && <>&ldquo;um&rdquo;/&ldquo;uh&rdquo; aren&apos;t detected with local recognition.</>}
    </p>
  );
}

/** The words the recogniser was least sure of, each with hear-it buttons. */
function UnclearWords({ clarity, voice, style }) {
  const [playing, setPlaying] = useState(null); // "word:slow" while its audio plays
  const [error, setError] = useState(null);

  const words = clarity?.unclear_words ?? [];
  if (words.length === 0) return null;

  async function hear(word, slow) {
    setError(null);
    setPlaying(`${word}:${slow}`);
    try {
      await playWord({ word, voice, style, slow });
    } catch (err) {
      setError(err.message);
    } finally {
      setPlaying((p) => (p === `${word}:${slow}` ? null : p));
    }
  }

  return (
    <div className="max-w-[30em] border border-panel-border bg-background px-3 py-2.5">
      <div className="text-right text-[9.5px] font-bold tracking-[0.16em] text-mute uppercase">Hard to catch</div>
      <ul className="mt-1.5 flex flex-wrap justify-end gap-x-4 gap-y-2">
        {words.map((w) => (
          <li key={`${w.word}-${w.start}`} className="flex items-center gap-1.5 text-[13px]">
            <span className="font-bold">{w.word}</span>
            <span className="text-[11px] text-mute" title="How confidently this word was recognised">
              {Math.round(w.probability * 100)}%
            </span>
            <PlayButton label={`Hear "${w.word}"`} active={playing === `${w.word}:false`} onClick={() => hear(w.word, false)}>
              hear
            </PlayButton>
            <PlayButton label={`Hear "${w.word}" slowly`} active={playing === `${w.word}:true`} onClick={() => hear(w.word, true)}>
              slow
            </PlayButton>
          </li>
        ))}
      </ul>
      {error && <p className="mt-1.5 text-right text-[11px] text-mute">{error}</p>}
    </div>
  );
}

function PlayButton({ label, active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={`flex cursor-pointer items-center gap-1 border px-1.5 py-0.5 text-[9.5px] font-bold tracking-[0.1em] uppercase transition ${
        active ? "border-brand bg-brand text-on-brand" : "border-panel-border text-soft hover:border-brand hover:text-brand"
      }`}
    >
      <svg viewBox="0 0 24 24" className="h-2.5 w-2.5" fill="currentColor" aria-hidden="true">
        <path d="M7 4.5v15a1 1 0 0 0 1.5.86l12-7.5a1 1 0 0 0 0-1.72l-12-7.5A1 1 0 0 0 7 4.5Z" />
      </svg>
      {children}
    </button>
  );
}

function fillerText(breakdown) {
  return Object.entries(breakdown || {})
    .map(([word, n]) => `${word} ×${n}`)
    .join(", ");
}

function Chip({ children, strong, muted, title }) {
  return (
    <span
      title={title}
      className={`border px-2 py-0.5 text-[9.5px] font-bold tracking-[0.1em] whitespace-nowrap uppercase ${
        strong ? "border-brand text-brand" : muted ? "border-panel-border text-mute" : "border-panel-border text-soft"
      }`}
    >
      {children}
    </span>
  );
}
