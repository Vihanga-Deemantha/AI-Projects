"use client";

import { faceSrc, getCompanion } from "@/lib/characters";

const heading = "text-[10px] font-bold tracking-[0.2em] text-soft uppercase";
const rowLabel = "text-[11px] font-bold tracking-[0.14em] text-mute uppercase";

/**
 * Companion / speaking style / scenario picker, sourced from
 * GET /api/config/options (backend/routers/config.py) so this never
 * hand-duplicates personalities.py.
 *
 * Pre-session: the full picker. In-session: collapses to a compact read-only
 * summary so the choices can't change under a running conversation.
 */
export default function SessionSetup({ options, value, onChange, sessionActive }) {
  if (!options) {
    return (
      <div className="border border-panel-border bg-panel p-5 text-sm text-mute">
        Loading session options…
      </div>
    );
  }

  if (sessionActive) {
    const voice = options.voices.find((v) => v.id === value.voice);
    const style = options.styles.find((s) => s.id === value.style);
    const scenario = options.scenarios.find((s) => s.id === value.scenario);
    return (
      <div className="flex flex-wrap items-center gap-2 border border-panel-border bg-panel px-5 py-3.5">
        <SummaryPill label="Companion" value={voice?.label} />
        <SummaryPill label="Style" value={style?.label} />
        <SummaryPill label="Scenario" value={scenario?.label} />
      </div>
    );
  }

  const activeStyle = options.styles.find((s) => s.id === value.style);

  return (
    <div className="border border-panel-border bg-panel p-5">
      <div className={heading}>Session setup</div>

      <div className="mt-4">
        <div className={rowLabel}>Companion</div>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {options.voices.map((v) => {
            const active = v.id === value.voice;
            return (
              <button
                key={v.id}
                type="button"
                onClick={() => onChange({ ...value, voice: v.id })}
                aria-pressed={active}
                className={`flex cursor-pointer items-center gap-2 border py-1.5 pr-3.25 pl-1.5 text-[12.5px] whitespace-nowrap transition ${
                  active ? "border-brand bg-brand-soft font-bold" : "border-panel-border font-medium hover:border-brand"
                }`}
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
          {options.styles.map((s) => (
            <Chip key={s.id} active={s.id === value.style} onClick={() => onChange({ ...value, style: s.id })}>
              {s.label}
            </Chip>
          ))}
        </div>
        <p className="mt-2.5 text-[11.5px] leading-normal text-mute">
          {activeStyle?.desc ? `${activeStyle.desc} — ` : ""}changes vocabulary &amp; phrasing, not the voice&apos;s accent.
        </p>
      </div>

      <div className="mt-4.5">
        <div className={rowLabel}>Scenario</div>
        <div className="mt-2.5 flex flex-wrap">
          {options.scenarios.map((s) => (
            <Chip key={s.id} active={s.id === value.scenario} onClick={() => onChange({ ...value, scenario: s.id })}>
              {s.label}
            </Chip>
          ))}
        </div>
      </div>
    </div>
  );
}

function Chip({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`-mr-px -mb-px cursor-pointer border px-3.5 py-2.25 text-[12.5px] whitespace-nowrap transition ${
        active ? "border-brand bg-brand font-bold text-on-brand" : "border-panel-border font-medium text-soft hover:border-brand"
      }`}
    >
      {children}
    </button>
  );
}

function SummaryPill({ label, value }) {
  return (
    <span className="bg-brand-soft px-3 py-1.25 text-[11px] font-bold tracking-widest text-soft uppercase">
      {label}: <span className="text-foreground">{value || "—"}</span>
    </span>
  );
}
