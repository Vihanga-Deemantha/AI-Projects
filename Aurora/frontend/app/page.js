"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { isLoggedIn } from "@/lib/auth";
import { CAST, SCENES, faceSrc, preload, sceneSrc, spriteSrc } from "@/lib/characters";
import { usePointerVars, useParallax, usePrefersReducedMotion, useTicker } from "@/hooks/motion";
import Sprite, { SpriteCrossfade } from "@/components/Sprite";
import SoundBars from "@/components/SoundBars";
import ThemeToggle from "@/components/ThemeToggle";

// One clock per rhythm: the roster's pose beat and the hero's relay turn are
// separate so either can be retimed on its own. A pose reads in about two
// seconds; the hero holds longer because a signature pose is an introduction.
const BEAT = 2200;
const HERO_TURN = 3000;
const POSE_LOOP = ["idle", "talking_open", "listening", "talking_emphatic"];
const HERO_ROUNDS = ["talking_open", "laughing", "thinking", "wave", "talking_emphatic", "listening"];

// The relay passes down the cast. The first round is everyone's SIGNATURE
// pose; later rounds walk the ordinary poses, offset by cast position so a
// round is not six people doing the same thing.
function heroPose(turn) {
  const n = CAST.length;
  const round = Math.floor(turn / n);
  if (round === 0) return "signature";
  return HERO_ROUNDS[(round - 1 + (turn % n)) % HERO_ROUNDS.length];
}

const TRANSCRIPT = [
  { who: "ai", text: "So — how has your week actually been? Give me the honest version." },
  { who: "me", text: "It was busy. I have been work on a presentation since Monday." },
  { who: "ai", text: "That sounds relentless. Is it for your team, or for a client?" },
  { who: "me", text: "For a client. I am little nervous about the questions part." },
];

const CORRECTIONS = [
  { was: "I have been work on", now: "I have been working on", why: "Present perfect continuous needs the -ing form after 'have been'." },
  { was: "I am little nervous", now: "I am a little nervous", why: "'A little' takes the article when it modifies an adjective." },
  { was: "the questions part", now: "the Q&A", why: "More natural in a work context — and shorter to say." },
];

const STATS = [
  { value: "12", label: "Day streak", note: "Sample dashboard" },
  { value: "3h 40m", label: "Spoken this month", note: "Sample dashboard" },
  { value: "86", label: "Corrections resolved", note: "Of 104 raised" },
  { value: "7/7", label: "Scenarios tried", note: "All settings visited" },
];

const CHART = [14, 12, 13, 9, 10, 7, 6, 4];

const eyebrow = "text-[10px] font-bold tracking-[0.24em] text-soft uppercase";
const chapterTitle = "mt-3 font-display text-[clamp(32px,5.4vw,72px)] leading-none font-semibold";
const navLink = "text-[10.5px] font-bold tracking-[0.22em] text-soft uppercase transition hover:text-brand";
const sectionBase = "relative flex min-h-screen flex-col justify-center gap-8 overflow-hidden px-5 pt-26 pb-17.5 md:px-11 max-lg:min-h-0 max-lg:pt-24 max-lg:pb-17.5";

export default function HomePage() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [focus, setFocus] = useState(0);
  const [scene, setScene] = useState(0);

  const calm = usePrefersReducedMotion();
  const [beat, setBeat] = useTicker(BEAT, !calm);
  const [heroTurn] = useTicker(HERO_TURN, !calm);

  usePointerVars(!calm);
  useParallax(!calm);

  // After mount: localStorage is unavailable during SSR, so the page renders
  // logged-out first and adjusts once hydrated. Also decode the upcoming
  // relay/roster frames so a crossfade never waits on the network.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is client-only; reading it during render would mismatch SSR output
    setLoggedIn(isLoggedIn());
    const frames = [];
    for (let t = 1; t <= 6; t++) frames.push(spriteSrc(CAST[t % CAST.length].id, heroPose(t)));
    for (const c of CAST) for (const p of POSE_LOOP) frames.push(spriteSrc(c.id, p));
    for (const s of SCENES) frames.push(sceneSrc(s.key));
    preload(frames);
  }, []);

  const n = CAST.length;
  const active = CAST[focus];
  const activeScene = SCENES[scene];
  const heroChar = CAST[heroTurn % n];
  const heroPoseName = heroPose(heroTurn);
  const maxFix = Math.max(...CHART);

  function pickChar(i) {
    setFocus(i);
    setBeat(0);
  }

  const startHref = loggedIn ? "/practice" : "/signup";

  // Roster: focus in the centre, two flanking, two cropped at the edges.
  const roster = [-2, -1, 0, 1, 2].map((o) => {
    const idx = (focus + o + n * 2) % n;
    const scale = [0.62, 0.86, 1.34, 0.86, 0.62][o + 2];
    const pose = o === 0 ? POSE_LOOP[beat % POSE_LOOP.length] : Math.abs(o) === 2 ? "idle_angled" : "listening";
    return { o, idx, scale, pose, c: CAST[idx] };
  });

  return (
    <div className="overflow-x-hidden bg-background text-foreground">
      <header className="fixed inset-x-0 top-0 z-60 flex h-18.5 items-center justify-between gap-6 border-b border-panel-border bg-background/90 px-5 backdrop-blur md:px-11">
        <a href="#s1" className="font-display text-[25px] font-bold tracking-[0.16em]">AURA</a>
        <nav className="hidden items-center gap-8 lg:flex">
          <a href="#s2" className={navLink}>Characters</a>
          <a href="#s3" className={navLink}>Scenarios</a>
          <a href="#s4" className={navLink}>Practice</a>
          <a href="#s5" className={navLink}>Progress</a>
        </nav>
        <div className="flex items-center gap-2.5">
          <ThemeToggle />
          {!loggedIn && (
            <Link href="/login" className="hidden h-9 items-center px-2 text-[10px] font-bold tracking-[0.18em] whitespace-nowrap text-soft uppercase transition hover:text-brand sm:inline-flex">
              Log in
            </Link>
          )}
          <Link
            href={startHref}
            className="inline-flex h-9 items-center border border-foreground px-5 text-[10px] font-bold tracking-[0.18em] whitespace-nowrap uppercase transition hover:border-brand hover:bg-brand hover:text-on-brand"
          >
            {loggedIn ? "Go to practice" : "Start speaking"}
          </Link>
        </div>
      </header>

      <main>
        {/* ── 01 Meet AURA ─────────────────────────────────────────────── */}
        <section id="s1" className="relative grid min-h-screen grid-cols-1 items-center gap-10 overflow-hidden px-5 pt-26 pb-17.5 md:px-11 max-lg:min-h-0 max-lg:pt-24 max-lg:pb-17.5 lg:grid-cols-[minmax(0,1.02fr)_minmax(0,0.98fr)]">
          <div data-par="0.16" className="absolute top-[6%] right-[-6%] aspect-square w-[min(620px,58vw)] rounded-full bg-brand-soft" />
          <div data-par="0.05" className="absolute inset-x-0 bottom-0 h-[22%] bg-brand-soft" />
          <div data-par="0.3" className="absolute inset-y-0 left-[8%] w-px bg-panel-border max-lg:hidden" />
          <div data-par="0.42" className="absolute inset-y-0 right-[26%] w-px bg-panel-border max-lg:hidden" />

          <div className="relative z-2">
            <div className={`aura-rise flex items-center gap-3 ${eyebrow}`}>
              <span className="aura-blink h-1.75 w-1.75 bg-brand" />
              Six companions · one coach
            </div>
            <h1 className="aura-rise mt-6 font-display text-[clamp(42px,7.4vw,112px)] leading-[0.94] font-semibold tracking-[-0.02em]">
              Meet AURA.
              <br />
              <em className="font-normal">Say something.</em>
            </h1>
            <p className="aura-rise mt-6 max-w-[27em] text-[16.5px] leading-[1.62] text-soft">
              Six speaking companions, each with their own voice and temperament. They hold a real English conversation with you, then tell you exactly what to fix.
            </p>
            <div className="aura-rise mt-9 flex w-fit flex-wrap border border-foreground">
              <a href="#s2" className="inline-flex h-13.5 items-center bg-foreground px-7.5 text-[11px] font-bold tracking-[0.18em] text-background uppercase transition hover:bg-brand hover:text-on-brand">
                Meet them
              </a>
              <a href="#s4" className="inline-flex h-13.5 items-center px-7.5 text-[11px] font-bold tracking-[0.18em] uppercase transition hover:bg-brand-soft">
                See a session
              </a>
            </div>
            <div className="aura-rise mt-13 flex flex-wrap gap-x-8 gap-y-4 border-t border-panel-border pt-6 sm:gap-x-11">
              {[["6", "Companions"], ["7", "Scenarios"], ["2s", "To a reply"]].map(([v, l]) => (
                <div key={l}>
                  <div className="font-display text-[30px]">{v}</div>
                  <div className="mt-0.5 text-[10px] font-bold tracking-[0.2em] text-soft uppercase">{l}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="relative z-2 grid min-h-[min(60vh,460px)] place-items-end justify-center lg:min-h-[min(78vh,620px)]">
            <div className="relative h-[min(60vh,460px)] w-full lg:h-[min(78vh,620px)]">
              <SoundBars count={26} barWidth={5} className="absolute inset-x-0 bottom-0 z-0 h-9.5 justify-between opacity-50" />
              <button
                type="button"
                onClick={() => pickChar(heroTurn % n)}
                aria-label={`Meet ${heroChar.name}`}
                className="group relative z-2 flex h-full w-full cursor-pointer items-end justify-center"
              >
                <div
                  className="relative mx-auto h-full max-w-full origin-[50%_98%] transition-[translate,scale] duration-500 group-hover:scale-[1.03]"
                  style={{ aspectRatio: "700 / 680", translate: "calc(var(--px, 0) * 14px) 0" }}
                >
                  <div className="absolute bottom-[1.2%] left-[32%] h-[1.6%] w-[36%] rounded-full bg-foreground opacity-[0.17] blur-sm" />
                  <SpriteCrossfade
                    src={spriteSrc(heroChar.id, heroPoseName)}
                    alt={`${heroChar.name}, ${heroPoseName.replace(/_/g, " ")}`}
                    className="absolute inset-0"
                  />
                </div>
              </button>
            </div>
          </div>
        </section>

        {/* ── 02 Meet the characters ───────────────────────────────────── */}
        <section id="s2" className={`${sectionBase} bg-panel`}>
          <div data-par="0.1" className="absolute inset-x-0 top-[34%] h-px bg-panel-border" />
          <div data-par="0.22" className="absolute bottom-[-18%] left-[-10%] aspect-square w-[min(520px,50vw)] rounded-full bg-brand-soft" />

          <div className="relative flex flex-wrap items-end justify-between gap-5">
            <div className="aura-slide">
              <div className={eyebrow}>Chapter two</div>
              <h2 className={chapterTitle}>Meet the characters</h2>
            </div>
            <div className="flex border border-panel-border">
              <button type="button" aria-label="Previous companion" onClick={() => pickChar((focus - 1 + n) % n)} className="h-11.5 w-13 cursor-pointer border-r border-panel-border text-[15px] transition hover:bg-brand-soft">&larr;</button>
              <button type="button" aria-label="Next companion" onClick={() => pickChar((focus + 1) % n)} className="h-11.5 w-13 cursor-pointer text-[15px] transition hover:bg-brand-soft">&rarr;</button>
            </div>
          </div>

          <div
            className="relative flex min-h-[min(56vh,440px)] items-end justify-center gap-[clamp(4px,2vw,34px)]"
            style={{ "--lead": "clamp(96px, 26vw, 250px)" }}
          >
            {roster.map(({ o, idx, scale, pose, c }) => (
              <button
                key={o}
                type="button"
                onClick={() => pickChar(idx)}
                aria-label={`Show ${c.name}`}
                className={`group flex shrink-0 cursor-pointer items-end transition-opacity duration-500 ${Math.abs(o) === 2 ? "max-sm:hidden" : ""}`}
                style={{ opacity: o === 0 ? 1 : Math.abs(o) === 1 ? 0.72 : 0.34, zIndex: 10 - Math.abs(o) }}
              >
                <div
                  className="relative origin-bottom transition-[translate,scale] duration-500 ease-[cubic-bezier(.34,1.46,.64,1)] group-hover:-translate-y-4 group-hover:scale-105"
                  style={{
                    height: `calc(var(--lead) * ${scale})`,
                    aspectRatio: "700 / 680",
                    rotate: "calc(var(--px, 0) * 1.9deg)",
                  }}
                >
                  <div className="absolute bottom-[-1.5%] left-[8%] h-[3.5%] w-[84%] rounded-full bg-foreground opacity-[0.16] blur-[7px] transition-opacity group-hover:opacity-[0.1]" />
                  {o === 0 ? (
                    <SpriteCrossfade src={spriteSrc(c.id, pose)} alt={`${c.name}, AURA speaking companion`} className="absolute inset-0" />
                  ) : (
                    <Sprite src={spriteSrc(c.id, pose)} alt={`${c.name}, AURA speaking companion`} className="absolute inset-0" />
                  )}
                </div>
              </button>
            ))}
          </div>

          <div className="relative grid items-start gap-10 border-t border-panel-border pt-6.5 lg:grid-cols-[minmax(0,0.44fr)_minmax(0,0.56fr)]">
            <div>
              <div className="flex flex-wrap items-baseline gap-3.5">
                <h3 className="font-display text-[clamp(34px,4.4vw,56px)] leading-none font-semibold">{active.name}</h3>
                <span className="text-[10px] font-bold tracking-[0.2em] text-brand uppercase">{active.tag}</span>
              </div>
              <div className="mt-2.5 font-display text-[19px] text-soft italic">{active.tagline}</div>
            </div>
            <div>
              <p className="max-w-[34em] text-[15.5px] leading-[1.68] text-soft">{active.blurb}</p>
              <div className="mt-5 flex flex-wrap">
                {active.traits.map((t) => (
                  <span key={t} className="-mr-px -mb-px border border-panel-border px-3.75 py-2 text-[11px] font-bold tracking-widest text-soft uppercase">{t}</span>
                ))}
              </div>
              <div className="mt-6 flex flex-wrap gap-5">
                <Link href={startHref} className="inline-flex h-12 items-center bg-brand px-6.5 text-[11px] font-bold tracking-[0.18em] text-on-brand uppercase transition hover:bg-foreground hover:text-background">
                  Practise with {active.name}
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* ── 03 Scenarios ─────────────────────────────────────────────── */}
        <section id="s3" className={sectionBase}>
          <div data-par="0.08" className="absolute inset-x-0 bottom-0 h-[26%] bg-brand-soft" />
          <div data-par="0.26" className="absolute top-[12%] right-[8%] aspect-square w-[min(360px,34vw)] bg-brand-soft max-lg:hidden" />

          <div className="aura-slide relative max-w-[34em]">
            <div className={eyebrow}>Chapter three</div>
            <h2 className={chapterTitle}>Enter different scenarios</h2>
          </div>

          <div className="relative grid items-stretch gap-11 lg:grid-cols-[minmax(0,0.34fr)_minmax(0,0.66fr)]">
            <div className="flex flex-col border-t border-panel-border bg-background">
              {SCENES.map((s, k) => (
                <button
                  key={s.key}
                  type="button"
                  onClick={() => setScene(k)}
                  className={`flex w-full cursor-pointer items-center gap-3.5 border-b border-panel-border px-1 py-4 text-[15px] transition ${
                    k === scene ? "bg-brand-soft font-bold text-foreground" : "font-medium text-soft"
                  }`}
                >
                  <span className="w-6.5 flex-none text-left font-display text-[13px]">{String(k + 1).padStart(2, "0")}</span>
                  <span className="flex-1 text-left">{s.label}</span>
                  <span className={`h-px w-5.5 ${k === scene ? "bg-brand" : "bg-transparent"}`} />
                </button>
              ))}
            </div>

            <div className="relative grid min-h-[min(52vh,420px)] border border-panel-border bg-panel md:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
              <div className="flex flex-col justify-between gap-5 border-b border-panel-border p-7.5 md:border-r md:border-b-0">
                <div>
                  <div className="text-[10px] font-bold tracking-[0.24em] text-brand uppercase">The setting</div>
                  <h3 className="mt-3.5 font-display text-[30px] leading-[1.08] font-semibold">{activeScene.label}</h3>
                  <p className="mt-3.5 text-[15px] leading-[1.64] text-soft">{activeScene.setting}</p>
                </div>
                <div>
                  <div className="text-[10px] font-bold tracking-[0.2em] text-mute uppercase">You will need</div>
                  <div className="mt-3 flex flex-wrap">
                    {activeScene.skills.map((s) => (
                      <span key={s} className="-mr-px -mb-px border border-panel-border px-3.25 py-1.75 text-[11px] font-semibold text-soft">{s}</span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="relative grid grid-rows-[auto_minmax(0,1fr)] gap-3.5 overflow-hidden bg-background px-5.5 pt-5.5">
                <div className="absolute inset-x-0 bottom-0 h-[16%] bg-brand-soft" />
                <div className="relative z-2 border border-foreground bg-panel px-4.5 py-3.75 text-[14.5px] leading-normal">{activeScene.line}</div>
                <div className="relative flex h-[clamp(235px,34vh,390px)] items-end justify-center pb-1.5">
                  <SpriteCrossfade src={sceneSrc(activeScene.key)} alt={`${activeScene.label} scenario`} className="relative z-1 h-full w-full" />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── 04 Practise English ──────────────────────────────────────── */}
        <section id="s4" className={`${sectionBase} bg-panel`}>
          <div data-par="0.14" className="absolute top-[-10%] right-[-8%] aspect-square w-[min(480px,44vw)] rounded-full bg-brand-soft" />

          <div className="aura-slide relative max-w-[34em]">
            <div className={eyebrow}>Chapter four</div>
            <h2 className={chapterTitle}>Practise English</h2>
          </div>

          <div className="relative grid lg:grid-cols-[minmax(0,1.3fr)_minmax(0,0.7fr)]">
            <div className="border border-panel-border bg-background">
              <div className="flex items-center justify-between gap-4 border-b border-panel-border px-5.5 py-4">
                <div className="flex items-center gap-3">
                  <span className="h-2.5 w-2.5 bg-brand" />
                  <span className="font-display text-[17px]">{active.name}</span>
                  <span className="text-[10px] font-bold tracking-[0.18em] text-mute uppercase">{activeScene.label}</span>
                </div>
                <span className="inline-flex items-center gap-2 text-[10px] font-bold tracking-[0.16em] text-soft uppercase">
                  <span className="aura-blink h-1.5 w-1.5 bg-brand" />1.4s
                </span>
              </div>
              <div className="flex flex-col gap-3.5 px-5.5 py-6">
                {TRANSCRIPT.map((t, i) => (
                  <div key={i} className={`flex items-end gap-2.25 ${t.who === "me" ? "flex-row-reverse" : ""}`}>
                    {t.who === "me" ? (
                      <div className="h-7.5 w-7.5 flex-none rounded-full bg-brand opacity-90" aria-label="You" />
                    ) : (
                      <div
                        role="img"
                        aria-label={active.name}
                        className="h-7.5 w-7.5 flex-none rounded-full bg-brand-soft bg-cover bg-top"
                        style={{ backgroundImage: `url('${faceSrc(active.id, i === 2 ? "speaking" : "neutral")}')` }}
                      />
                    )}
                    <div className={`max-w-[74%] px-4.5 py-3.5 text-[15px] leading-[1.55] ${t.who === "me" ? "bg-brand-soft" : "border border-panel-border bg-panel"}`}>
                      {i === 0 ? activeScene.line : t.text}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-4.5 border-t border-panel-border px-5.5 py-4.5">
                <div className="grid h-11.5 w-11.5 place-items-center bg-brand">
                  <span className="block h-4.5 w-2.5 bg-on-brand" />
                </div>
                <SoundBars count={22} barWidth={3} wave="cos" freq={1.1} delayStep={0.06} baseDuration={0.85} barClassName="bg-brand" className="h-7 gap-1" />
                <span className="ml-auto text-[10px] font-bold tracking-[0.18em] text-mute uppercase">Hold to speak</span>
              </div>
            </div>

            <div className="border border-panel-border bg-background max-lg:border-t-0 lg:border-l-0">
              <div className="border-b border-panel-border px-5.5 py-4 text-[10px] font-bold tracking-[0.24em] text-brand uppercase">Corrections</div>
              {CORRECTIONS.map((fix) => (
                <div key={fix.was} className="border-b border-panel-border px-5.5 py-5">
                  <div className="flex flex-wrap items-center gap-2.25 text-[14.5px]">
                    <span className="text-mute line-through">{fix.was}</span>
                    <span className="text-brand">&rarr;</span>
                    <span className="font-bold">{fix.now}</span>
                  </div>
                  <div className="mt-2 text-[12.5px] leading-[1.55] text-soft">{fix.why}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── 05 Track your improvement ────────────────────────────────── */}
        <section id="s5" className={sectionBase}>
          <div data-par="0.2" className="absolute top-[8%] left-[-6%] aspect-square w-[min(420px,40vw)] rounded-full bg-brand-soft" />

          <div className="aura-slide relative max-w-[34em]">
            <div className={eyebrow}>Chapter five</div>
            <h2 className={chapterTitle}>Track your improvement</h2>
            <p className="mt-4 text-base leading-[1.62] text-soft">Every session lands in your speech history. The mistakes you stop making are the measure.</p>
          </div>

          <div className="aura-rise relative flex flex-wrap">
            {STATS.map((s) => (
              <div key={s.label} className="-mr-px -mb-px flex-[1_1_190px] border border-panel-border bg-panel p-6.5">
                <div className="font-display text-[46px] leading-none">{s.value}</div>
                <div className="mt-3 text-[10px] font-bold tracking-[0.2em] uppercase">{s.label}</div>
                <div className="mt-1.25 text-xs text-soft">{s.note}</div>
              </div>
            ))}
          </div>

          <div className="aura-rise relative border border-panel-border bg-panel p-7.5">
            <div className="flex flex-wrap items-baseline justify-between gap-4">
              <h4 className="font-display text-[22px] font-semibold">Corrections per session</h4>
              <span className="text-[10px] font-bold tracking-[0.18em] text-mute uppercase">Sample month · fewer is better</span>
            </div>
            <div className="mt-7 flex h-45 items-end gap-3">
              {CHART.map((v, i) => (
                <div key={i} className="flex h-full flex-1 flex-col items-center justify-end gap-2.5">
                  <div className="text-[11px] font-bold text-soft">{v}</div>
                  <div className="w-full bg-brand" style={{ height: `${Math.round((v / maxFix) * 100)}%` }} />
                  <div className="text-[10px] tracking-widest text-mute">{String(i + 1).padStart(2, "0")}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── 06 Start speaking ────────────────────────────────────────── */}
        <section id="s6" className="relative flex min-h-screen flex-col justify-end overflow-hidden bg-panel px-5 pt-26 md:px-11 max-lg:min-h-0">
          <div className="aura-slide relative max-w-[26em] pb-10.5">
            <div className={eyebrow}>Chapter six</div>
            <h2 className="mt-3.5 font-display text-[clamp(40px,7vw,104px)] leading-[0.96] font-semibold">
              Start <em>speaking.</em>
            </h2>
            <p className="mt-5 text-[16.5px] leading-[1.6] text-soft">One conversation is enough to see where you stand. All six are waiting.</p>
            <div className="mt-7.5 flex flex-wrap items-center gap-6.5">
              <Link href={startHref} className="inline-flex h-14 items-center bg-foreground px-8 text-[11px] font-bold tracking-[0.18em] text-background uppercase transition hover:bg-brand hover:text-on-brand">
                {loggedIn ? "Go to practice" : "Start speaking free"}
              </Link>
              {!loggedIn && (
                <Link href="/login" className="border-b border-panel-border pb-0.75 text-[11px] font-bold tracking-[0.18em] text-soft uppercase transition hover:border-brand hover:text-brand">
                  I already have an account
                </Link>
              )}
            </div>
          </div>

          <div className="relative -mx-5 bg-brand-soft px-5 md:-mx-11 md:px-11">
            <div className="relative flex min-h-[min(42vh,340px)] items-end justify-center gap-[clamp(2px,1.4vw,22px)]">
              {CAST.map((c, k) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => pickChar(k)}
                  aria-label={`Show ${c.name}`}
                  className={`group flex shrink-0 cursor-pointer items-end transition-opacity duration-500 ${k === focus ? "opacity-100" : "opacity-55"}`}
                >
                  <div
                    className="aura-figure relative origin-bottom transition-[translate,scale] duration-500 ease-[cubic-bezier(.34,1.46,.64,1)] group-hover:-translate-y-4 group-hover:scale-105"
                    style={{ height: "clamp(58px, 15vw, 186px)", aspectRatio: "700 / 680", rotate: "calc(var(--px, 0) * 1.9deg)" }}
                  >
                    <div className="absolute bottom-[-1.5%] left-[8%] h-[3.5%] w-[84%] rounded-full bg-foreground opacity-[0.16] blur-[5px]" />
                    <Sprite src={spriteSrc(c.id, "idle")} alt={`${c.name}, AURA speaking companion`} className="absolute inset-0" />
                  </div>
                </button>
              ))}
            </div>

            <footer className="relative flex flex-wrap items-center justify-between gap-5 border-t border-panel-border py-5.5">
              <span className="font-display text-lg tracking-[0.16em]">AURA</span>
              <p className="max-w-[46em] text-[11.5px] leading-[1.55] text-soft">
                Speaking styles change vocabulary and phrasing, informed by regional English — not claims of accent reproduction.
              </p>
            </footer>
          </div>
        </section>
      </main>
    </div>
  );
}
