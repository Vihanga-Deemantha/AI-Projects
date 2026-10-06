"use client";

import Link from "next/link";
import DifficultyLabel from "@/components/DifficultyLabel";
import { speaks, styleAccent, whyNot, withArticle } from "@/lib/accents";
import { companionHint, faceSrc, getCompanion } from "@/lib/characters";

const heading = "text-[10px] font-bold tracking-[0.2em] text-soft uppercase";
const rowLabel = "text-[11px] font-bold tracking-[0.14em] text-mute uppercase";

/**
 * Companion / speaking style / scenario picker, sourced from
 * GET /api/config/options (backend/routers/config.py) so this never
 * hand-duplicates personalities.py.
 *
 * Always the same panel, in the same spot — it never gets swapped out for a
 * different layout. While a session is live the chips just lock (dimmed,
 * unclickable) so the choices can't change under a running conversation;
 * they unlock again the moment the session ends.
 *
 * A speaking style brings an accent, and not every companion has a voice for every accent, so
 * a companion or style the other choice can't go with is dimmed, with the reason on hover.
 *
 * `difficulty` is the level to show — the one the next session will run at, or the
 * running session's own. It is chosen on the profile (or automatically), not here.
 */
export default function SessionSetup({ options, value, onChange, sessionActive, difficulty }) {
  if (!options) {
    return (
      <div className="border border-panel-border bg-panel p-5 text-sm text-mute">
        Loading session options…
      </div>
    );
  }

  const activeStyle = options.styles.find((s) => s.id === value.style);
  const accentNow = styleAccent(options, value.style);
  const speaker = options.voices.find((v) => v.id === value.voice);
  const name = speaker?.label ?? "Your companion";
  const example = difficulty && options.difficulties?.find((d) => d.level === difficulty.tier)?.example;

  return (
    <div className={`border border-panel-border bg-panel p-5 transition-opacity ${sessionActive ? "opacity-60" : ""}`}>
      <div className="flex items-center justify-between gap-3">
        <div className={heading}>Session setup</div>
        {sessionActive && (
          <span className="text-[10px] font-bold tracking-[0.14em] text-mute uppercase">Locked during session</span>
        )}
      </div>

      <div className="mt-4">
        <div className={rowLabel}>Companion</div>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {options.voices.map((v) => {
            const active = v.id === value.voice;
            const can = speaks(options, v.id, value.style);
            return (
              <button
                key={v.id}
                type="button"
                onClick={() => onChange({ ...value, voice: v.id })}
                disabled={sessionActive || !can}
                aria-pressed={active}
                title={can ? companionHint(getCompanion(v.id), accentNow) : whyNot(options, v.id, value.style)}
                className={`flex items-center gap-2 border py-1.5 pr-3.25 pl-1.5 text-[12.5px] whitespace-nowrap transition ${
                  sessionActive ? "cursor-not-allowed" : can ? "cursor-pointer" : "cursor-not-allowed opacity-40"
                } ${active ? "border-brand bg-brand-soft font-bold" : "border-panel-border font-medium hover:border-brand"}`}
              >
                <span
                  role="img"
                  aria-label={v.label}
                  className="h-5.5 w-5.5 flex-none rounded-full bg-brand-soft bg-cover bg-top"
                  style={{ backgroundImage: `url('${faceSrc(getCompanion(v.id).id, "neutral")}')` }}
                />
                {v.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-4.5">
        <div className={rowLabel}>Speaking style</div>
        <div className="mt-2.5 flex flex-wrap">
          {options.styles.map((s) => {
            const can = speaks(options, value.voice, s.id);
            return (
              <Chip
                key={s.id}
                active={s.id === value.style}
                disabled={sessionActive || !can}
                unavailable={!can && !sessionActive}
                title={can ? undefined : whyNot(options, value.voice, s.id)}
                onClick={() => onChange({ ...value, style: s.id })}
              >
                {s.label}
              </Chip>
            );
          })}
        </div>
        <p className="mt-2.5 text-[11.5px] leading-normal text-mute">
          {activeStyle?.desc && <span className="block">{activeStyle.desc}</span>}
          <span className="block">
            {accentNow
              ? `Your coach uses these words, and ${name} will speak with ${withArticle(accentNow)} accent.`
              : `${name}'s own voice${speaker?.accent ? ` (${speaker.accent} accent)` : ""}.`}
          </span>
        </p>
      </div>

      <div className="mt-4.5">
        <div className={rowLabel}>Scenario</div>
        <div className="mt-2.5 flex flex-wrap">
          {options.scenarios.map((s) => (
            <Chip key={s.id} active={s.id === value.scenario} disabled={sessionActive} onClick={() => onChange({ ...value, scenario: s.id })}>
              {s.label}
            </Chip>
          ))}
        </div>
      </div>

      {difficulty && (
        <div className="mt-4.5">
          <div className={rowLabel}>Difficulty</div>
          <div className="mt-2.5 flex flex-wrap items-baseline gap-x-3.5 gap-y-1">
            <DifficultyLabel level={difficulty} className="font-display text-[17px] leading-none font-bold" />
            {!sessionActive && (
              <Link
                href="/profile#difficulty"
                className="text-[10px] font-bold tracking-[0.14em] text-soft uppercase underline underline-offset-[3px] transition hover:text-brand"
              >
                Change
              </Link>
            )}
          </div>
          <p className="mt-2 text-[11.5px] leading-normal text-mute">
            {example && <span className="block">For example: &ldquo;{example}&rdquo;</span>}
            {!sessionActive && difficulty.reason && <span className="block">{difficulty.reason}</span>}
          </p>
        </div>
      )}
    </div>
  );
}

function Chip({ active, disabled, unavailable = false, title, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      title={title}
      className={`-mr-px -mb-px border px-3.5 py-2.25 text-[12.5px] whitespace-nowrap transition ${
        disabled ? "cursor-not-allowed" : "cursor-pointer"
      } ${unavailable ? "opacity-40" : ""} ${active ? "border-brand bg-brand font-bold text-on-brand" : "border-panel-border font-medium text-soft hover:border-brand"}`}
    >
      {children}
    </button>
  );
}
