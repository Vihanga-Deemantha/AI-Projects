"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getSessionReport } from "@/lib/api";
import { faceSrc, getCompanion, sceneLabel, styleLabel } from "@/lib/characters";
import { formatDuration } from "@/lib/format";
import { playWord } from "@/lib/wordAudio";

const POLL_MS = 2000;
const MAX_WAIT_MS = 60_000;

const DIMENSIONS = [
  { key: "grammar", label: "Grammar", hint: "Mistakes per 100 words, weighted by how serious they are" },
  { key: "vocabulary", label: "Vocabulary", hint: "Wrong words and word partnerships per 100 words" },
  { key: "fluency", label: "Fluency", hint: "Speaking rate, pauses, fillers and repetitions" },
  { key: "clarity", label: "Clarity", hint: "How confidently speech recognition identified your words — an estimate, not pronunciation scoring" },
  { key: "naturalness", label: "Naturalness", hint: "How natural your phrasing sounds; idioms and phrasal verbs add to it" },
];

/**
 * The end-of-session report: overall score, five dimension scores, what went well,
 * what to work on, the most common mistakes and words worth practising.
 *
 * Right after a session ends the report can still be "pending" for a few seconds
 * (the last turn's analysis is finishing), so this polls until it is ready.
 */
export default function SessionReportView({ conversationId, session }) {
  const [state, setState] = useState({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    let timer = null;
    const startedAt = Date.now();

    async function load() {
      try {
        const result = await getSessionReport(conversationId);
        if (cancelled) return;
        if (result.status === "pending" && Date.now() - startedAt < MAX_WAIT_MS) {
          setState({ status: "pending" });
          timer = setTimeout(load, POLL_MS);
          return;
        }
        setState(result.status === "pending" ? { status: "error", message: "The report is taking longer than usual. Try again in a minute." } : result);
      } catch (err) {
        if (!cancelled) setState({ status: "error", message: err.message });
      }
    }

    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [conversationId]);

  if (state.status === "loading" || state.status === "pending") {
    return (
      <div className="mt-8 border border-panel-border bg-panel p-8 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-panel-border border-t-brand" />
        <p className="mt-4 text-sm text-soft">
          {state.status === "pending" ? "Finishing the analysis of your last answer…" : "Loading your report…"}
        </p>
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <div role="alert" className="mt-8 border border-brand bg-brand-soft px-4 py-3 text-sm">
        {state.message}
      </div>
    );
  }
  if (state.status === "none") {
    return <p className="mt-8 border border-dashed border-panel-border p-8 text-center text-sm text-soft">{state.message}</p>;
  }
  if (state.status === "running") {
    return <p className="mt-8 border border-dashed border-panel-border p-8 text-center text-sm text-soft">This session is still going. End it to see your report.</p>;
  }

  return <Report report={state.report} session={session} />;
}

function Report({ report, session }) {
  const { scores, facts } = report;
  const who = getCompanion(session?.voice);

  return (
    <div className="mt-6 flex flex-col gap-5.5">
      {/* Overall */}
      <section className="grid gap-6 border border-panel-border bg-panel p-6.5 sm:grid-cols-[auto_1fr] sm:items-center">
        <ScoreRing value={scores.overall} />
        <div className="min-w-0">
          <div className="text-[10px] font-bold tracking-[0.2em] text-soft uppercase">
            {sceneLabel(session?.scenario)} · {styleLabel(session?.style)}
            {session?.difficulty ? ` · ${session.difficulty.label} level` : ""}
          </div>
          {report.summary ? (
            <div className="mt-3 flex items-start gap-3">
              <span
                role="img"
                aria-label={who.name}
                className="mt-0.5 h-9 w-9 flex-none rounded-full bg-brand-soft bg-cover bg-top"
                style={{ backgroundImage: `url('${faceSrc(who.id, "smiling")}')` }}
              />
              <p className="text-[15px] leading-[1.6]">{report.summary}</p>
            </div>
          ) : (
            <p className="mt-3 text-[15px] leading-[1.6] text-soft">Here is how that session went.</p>
          )}
        </div>
      </section>

      {/* Dimensions */}
      <section className="border border-panel-border bg-panel p-6.5">
        <h2 className="font-display text-xl font-bold">Scores</h2>
        <div className="mt-4.5 flex flex-col gap-4">
          {DIMENSIONS.map((d) => (
            <ScoreBar key={d.key} id={d.key} label={d.label} value={scores[d.key]} hint={d.hint} />
          ))}
        </div>
      </section>

      <div className="grid gap-5.5 md:grid-cols-2">
        <ListCard title="What went well" items={report.strengths} empty="Keep practising — strengths will show up here." tone="good" />
        <ListCard title="Work on next" items={report.improvements} empty="Nothing major to fix this session." tone="next" />
      </div>

      {report.top_errors.length > 0 && (
        <section className="border border-panel-border bg-panel">
          <h2 className="border-b border-panel-border px-6.5 py-4 font-display text-xl font-bold">Most common mistakes</h2>
          <ul>
            {report.top_errors.map((e) => (
              <li key={`${e.category}-${e.subtype}`} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-panel-border px-6.5 py-4 last:border-b-0">
                <span className="min-w-36 text-[13.5px] font-bold">{e.label}</span>
                <span className="text-[11px] font-bold tracking-[0.12em] text-brand uppercase">
                  {e.count} {e.count === 1 ? "time" : "times"}
                </span>
                <span className="text-[13.5px] text-soft">
                  <span className="text-mute line-through">{e.example_original}</span> &rarr; <span className="font-semibold text-foreground">{e.example_correction}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.practice_words.length > 0 && <PracticeWords words={report.practice_words} voice={session?.voice} style={session?.style} />}

      {/* Facts */}
      <div className="flex flex-wrap">
        <Fact value={facts.turns} label="Turns" />
        <Fact value={facts.words} label="Words spoken" />
        <Fact value={formatDuration(facts.duration_seconds)} label="Length" />
        {facts.avg_wpm != null && <Fact value={Math.round(facts.avg_wpm)} label="Words / min" />}
        <Fact value={facts.praise} label="Praised" />
      </div>

      <div className="flex flex-wrap gap-3">
        <Link
          href="/practice"
          className="inline-flex h-12 items-center bg-foreground px-6.5 text-[11px] font-bold tracking-[0.18em] text-background uppercase transition hover:bg-brand hover:text-on-brand"
        >
          Practise again
        </Link>
        <Link
          href={`/history/${report.conversation_id}`}
          className="inline-flex h-12 items-center border border-panel-border px-6.5 text-[11px] font-bold tracking-[0.18em] text-soft uppercase transition hover:border-brand hover:text-brand"
        >
          See the transcript
        </Link>
      </div>
    </div>
  );
}

function ScoreRing({ value }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const shown = value ?? 0;
  return (
    <div className="relative grid h-36 w-36 flex-none place-items-center" role="img" aria-label={value == null ? "No overall score" : `Overall score ${value} out of 100`}>
      <svg width="144" height="144" viewBox="0 0 144 144" className="-rotate-90" aria-hidden="true">
        <circle cx="72" cy="72" r={radius} fill="none" stroke="var(--panel-border)" strokeWidth="7" />
        <circle
          cx="72" cy="72" r={radius} fill="none" stroke="var(--brand)" strokeWidth="7"
          strokeDasharray={circumference.toFixed(1)}
          strokeDashoffset={(circumference * (1 - shown / 100)).toFixed(1)}
          style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(.22,1,.36,1)" }}
        />
      </svg>
      <div className="absolute text-center">
        <div className="font-display text-[44px] leading-none font-bold">{value ?? "—"}</div>
        <div className="mt-1 text-[10px] font-bold tracking-[0.18em] text-soft uppercase">Overall</div>
      </div>
    </div>
  );
}

/** One score with its bar. What the score measures is written under the label, not hidden in a tooltip. */
function ScoreBar({ id, label, value, hint }) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-[12.5px]">
        <span className="font-bold">{label}</span>
        <span className={value == null ? "text-mute" : "font-display text-base font-bold"}>
          {value == null ? "Not enough data" : value}
        </span>
      </div>
      <p id={`score-hint-${id}`} className="mt-0.5 text-xs leading-snug text-mute">{hint}</p>
      <div
        className="mt-1.75 h-1.75 bg-field"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value ?? 0}
        aria-label={label}
        aria-describedby={`score-hint-${id}`}
      >
        <div className="h-full bg-brand transition-[width] duration-700 motion-reduce:transition-none" style={{ width: `${value ?? 0}%` }} />
      </div>
    </div>
  );
}

function ListCard({ title, items, empty, tone }) {
  return (
    <section className="border border-panel-border bg-panel p-6.5">
      <h2 className="font-display text-xl font-bold">{title}</h2>
      {items.length === 0 ? (
        <p className="mt-3 text-[13.5px] text-mute">{empty}</p>
      ) : (
        <ul className="mt-3.5 flex flex-col gap-3">
          {items.map((text) => (
            <li key={text} className="flex gap-3 text-[14px] leading-[1.55]">
              <span className={`mt-1.75 h-1.75 w-1.75 flex-none ${tone === "good" ? "bg-brand" : "bg-mute"}`} aria-hidden="true" />
              {text}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function PracticeWords({ words, voice, style }) {
  const [playing, setPlaying] = useState(null);
  const [error, setError] = useState(null);

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
    <section className="border border-panel-border bg-panel p-6.5">
      <h2 className="font-display text-xl font-bold">Words to practise</h2>
      <p className="mt-2 text-[13px] text-soft">Speech recognition found these hardest to catch. Listen, then try them aloud.</p>
      <ul className="mt-4 flex flex-wrap gap-3">
        {words.map((w) => (
          <li key={w} className="flex items-center gap-2 border border-panel-border px-3.5 py-2.5">
            <span className="text-[14px] font-bold">{w}</span>
            {[false, true].map((slow) => (
              <button
                key={String(slow)}
                type="button"
                onClick={() => hear(w, slow)}
                aria-label={slow ? `Hear "${w}" slowly` : `Hear "${w}"`}
                className={`cursor-pointer border px-1.5 py-0.5 text-[10px] font-bold tracking-[0.1em] uppercase transition ${
                  playing === `${w}:${slow}` ? "border-brand bg-brand text-on-brand" : "border-panel-border text-soft hover:border-brand hover:text-brand"
                }`}
              >
                {slow ? "slow" : "hear"}
              </button>
            ))}
          </li>
        ))}
      </ul>
      {error && <p className="mt-3 text-[12px] text-mute">{error}</p>}
    </section>
  );
}

function Fact({ value, label }) {
  return (
    <div className="-mr-px -mb-px flex-[1_1_110px] border border-panel-border bg-panel p-4.5">
      <div className="font-display text-[26px] leading-none">{value ?? "—"}</div>
      <div className="mt-1.5 text-[10px] font-bold tracking-[0.16em] text-soft uppercase">{label}</div>
    </div>
  );
}
