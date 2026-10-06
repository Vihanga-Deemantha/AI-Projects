"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import LineChart from "@/components/LineChart";
import { getProgress, getWeaknesses } from "@/lib/api";
import { formatDay, formatHours, formatMinutes, shortDate } from "@/lib/format";

// Overall uses the brand colour; the rest are distinct hues defined per theme in globals.css (--series-*), each
// dark enough on the light panel and light enough on the dark one to be told from the background.
const SERIES = [
  { key: "overall", label: "Overall", color: "var(--brand)", bold: true },
  { key: "grammar", label: "Grammar", color: "var(--series-grammar)" },
  { key: "vocabulary", label: "Vocabulary", color: "var(--series-vocabulary)" },
  { key: "fluency", label: "Fluency", color: "var(--series-fluency)" },
  { key: "clarity", label: "Clarity", color: "var(--series-clarity)" },
  { key: "naturalness", label: "Naturalness", color: "var(--series-naturalness)" },
];

export default function Progress() {
  const [data, setData] = useState(null);
  const [weak, setWeak] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getProgress({ weeks: 12 })
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setStatus("error");
      });
    // The weakness profile is secondary: if it fails the rest of the page is still useful.
    getWeaknesses()
      .then((r) => !cancelled && setWeak(r.weaknesses))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="min-w-0 flex-1 px-5 py-7 sm:px-8 lg:px-10 lg:pt-9 lg:pb-14">
      <div className="max-w-215">
        <header>
          <div className="text-[10px] font-bold tracking-[0.22em] text-soft uppercase">Progress</div>
          <h1 className="mt-2.5 font-display text-[clamp(30px,3.6vw,46px)] leading-none font-bold">How you&apos;re improving</h1>
          <p className="mt-3 max-w-[38em] text-[15px] leading-[1.6] text-soft">
            Your scores week by week. Every finished session adds a point to the chart.
          </p>
        </header>

        {status === "loading" && <p className="mt-6.5 text-sm text-mute">Loading your progress…</p>}
        {status === "error" && <div role="alert" className="mt-6.5 border border-brand bg-brand-soft px-4 py-3 text-sm">{error}</div>}
        {status === "ready" && !data.has_data && <EmptyState />}
        {status === "ready" && data.has_data && <Dashboard data={data} weaknesses={weak} />}
      </div>
    </main>
  );
}

function EmptyState() {
  return (
    <div className="mt-6.5 border border-dashed border-panel-border p-10 text-center">
      <p className="text-sm text-soft">Finish a practice session and your progress starts here.</p>
      <Link
        href="/practice"
        className="mt-4 inline-flex h-12 items-center bg-foreground px-6.5 text-[11px] font-bold tracking-[0.18em] text-background uppercase transition hover:bg-brand hover:text-on-brand"
      >
        Start practising
      </Link>
    </div>
  );
}

function Dashboard({ data, weaknesses }) {
  const { totals, streak, weekly, milestones, recent, best_session: best } = data;
  const [selected, setSelected] = useState(["overall"]);

  const labels = weekly.map((w) => shortDate(w.week_start));
  const shown = SERIES.filter((s) => selected.includes(s.key)).map((s) => ({ ...s, values: weekly.map((w) => w[s.key]) }));
  const hasAnyScore = weekly.some((w) => w.overall != null);

  function toggle(key) {
    setSelected((cur) => (cur.includes(key) ? (cur.length > 1 ? cur.filter((k) => k !== key) : cur) : [...cur, key]));
  }

  return (
    <div className="mt-6.5 flex flex-col gap-5.5">
      <div className="flex flex-wrap">
        <Stat value={totals.sessions} label="Sessions" />
        <Stat value={formatHours(totals.practice_seconds)} label="Practice time" />
        <Stat value={best ? best.overall : "—"} label="Best score" />
        <div className="-mr-px -mb-px flex-[1_1_200px] border border-panel-border bg-panel p-4.5">
          <div className="flex items-baseline gap-2">
            <span className="font-display text-[26px] leading-none">{streak.current}</span>
            <span className="text-[12px] text-soft">{streak.current === 1 ? "day" : "days"}</span>
          </div>
          <div className="mt-2 flex gap-1" aria-label="Practice in the last 7 days">
            {streak.last_7_days.map((on, i) => (
              <span key={i} className={`h-2.5 w-full ${on ? "bg-brand" : "bg-field"}`} />
            ))}
          </div>
          <div className="mt-1.5 text-[10px] font-bold tracking-[0.16em] text-soft uppercase">
            Streak{streak.longest > streak.current ? ` · best ${streak.longest}` : ""}
          </div>
        </div>
      </div>

      <section className="border border-panel-border bg-panel p-6.5">
        <h2 className="font-display text-xl font-bold">Scores by week</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          {SERIES.map((s) => {
            const on = selected.includes(s.key);
            return (
              <button
                key={s.key}
                type="button"
                onClick={() => toggle(s.key)}
                aria-pressed={on}
                className={`flex cursor-pointer items-center gap-2 border px-3 py-1.5 text-xs font-bold transition ${
                  on ? "border-foreground" : "border-panel-border text-mute hover:border-brand"
                }`}
              >
                <span className="h-2.5 w-2.5" style={{ background: on ? s.color : "transparent", border: `2px solid ${s.color}` }} />
                {s.label}
              </button>
            );
          })}
        </div>
        <div className="mt-5">
          {hasAnyScore ? (
            <LineChart labels={labels} series={shown} />
          ) : (
            <p className="py-10 text-center text-sm text-mute">Your sessions so far don&apos;t have scores yet. The next one will.</p>
          )}
        </div>
      </section>

      {milestones.length > 0 && (
        <section className="border border-panel-border bg-panel p-6.5">
          <h2 className="font-display text-xl font-bold">Worth celebrating</h2>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {milestones.map((m) => (
              <li key={m.text} className="flex items-start gap-3 border border-panel-border bg-background px-4 py-3.5 text-[14px] leading-[1.5]">
                <span className="mt-1.5 h-2 w-2 flex-none bg-brand" aria-hidden="true" />
                {m.text}
              </li>
            ))}
          </ul>
        </section>
      )}

      {weaknesses.length > 0 && <FocusAreas weaknesses={weaknesses} />}

      <section className="border border-panel-border bg-panel">
        <h2 className="border-b border-panel-border px-6.5 py-4 font-display text-xl font-bold">Recent sessions</h2>
        <ul>
          {recent.map((r) => (
            <li key={r.conversation_id} className="border-b border-panel-border last:border-b-0">
              <Link
                href={`/history/${r.conversation_id}/report`}
                className="flex flex-wrap items-center gap-4 px-6.5 py-3.5 transition hover:bg-brand-soft/60"
              >
                <span className="min-w-28 text-[13.5px] font-bold">{formatDay(r.when)}</span>
                <span className="text-[12px] text-mute">
                  {r.turns} {r.turns === 1 ? "turn" : "turns"} · {formatMinutes(r.duration_seconds)}
                </span>
                <span className="ml-auto font-display text-lg font-bold text-brand">{r.overall ?? "—"}</span>
                <span className="text-[15px] text-mute" aria-hidden="true">&rarr;</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

const TREND = {
  improving: { text: "Improving", cls: "text-brand" },
  worsening: { text: "Slipping", cls: "text-foreground" },
  new: { text: "New", cls: "text-soft" },
  stable: { text: "Steady", cls: "text-mute" },
};

/** What the learner keeps getting wrong, with the trend and a one-click way to practise it. */
function FocusAreas({ weaknesses }) {
  return (
    <section className="border border-panel-border bg-panel">
      <div className="border-b border-panel-border px-6.5 py-4">
        <h2 className="font-display text-xl font-bold">Your focus areas</h2>
        <p className="mt-1.5 text-[13px] text-soft">The mistakes you make most, newest habits weighted highest.</p>
      </div>
      <ul>
        {weaknesses.slice(0, 5).map((w) => {
          const trend = TREND[w.trend] ?? TREND.stable;
          return (
            <li key={w.focus} className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-panel-border px-6.5 py-3.5 last:border-b-0">
              <span className="min-w-40 flex-[1_1_160px] text-[13.5px] font-bold">{w.label}</span>
              <span className="text-[12px] text-mute">
                {w.recent} in the last 30 days · {w.occurrences} in total
              </span>
              <span className={`text-[10px] font-bold tracking-[0.14em] uppercase ${trend.cls}`}>{trend.text}</span>
              {w.subtype !== "other" && (
                <Link
                  href={`/practice?focus=${encodeURIComponent(w.focus)}`}
                  className="ml-auto border border-panel-border px-3 py-1.5 text-[10px] font-bold tracking-[0.14em] text-soft uppercase transition hover:border-brand hover:text-brand"
                >
                  Practise &rarr;
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Stat({ value, label }) {
  return (
    <div className="-mr-px -mb-px flex-[1_1_130px] border border-panel-border bg-panel p-4.5">
      <div className="font-display text-[26px] leading-none">{value}</div>
      <div className="mt-1.5 text-[10px] font-bold tracking-[0.16em] text-soft uppercase">{label}</div>
    </div>
  );
}

