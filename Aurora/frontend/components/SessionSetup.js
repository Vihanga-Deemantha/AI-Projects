"use client";

import { faceSrc, getCompanion } from "@/lib/characters";

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
 */
export default function SessionSetup({ options, value, onChange, sessionActive }) {
  if (!options) {
    return (
      <div className="border border-panel-border bg-panel p-5 text-sm text-mute">
        Loading session options…
      </div>
    );
  }

  const activeStyle = options.styles.find((s) => s.id === value.style);

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
            return (
              <button
                key={v.id}
                type="button"
                onClick={() => onChange({ ...value, voice: v.id })}
                disabled={sessionActive}
                aria-pressed={active}
                className={`flex items-center gap-2 border py-1.5 pr-3.25 pl-1.5 text-[12.5px] whitespace-nowrap transition ${
                  sessionActive ? "cursor-not-allowed" : "cursor-pointer"
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
          {options.styles.map((s) => (
            <Chip key={s.id} active={s.id === value.style} disabled={sessionActive} onClick={() => onChange({ ...value, style: s.id })}>
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
            <Chip key={s.id} active={s.id === value.scenario} disabled={sessionActive} onClick={() => onChange({ ...value, scenario: s.id })}>
              {s.label}
            </Chip>
          ))}
        </div>
      </div>
    </div>
  );
}

function Chip({ active, disabled, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      className={`-mr-px -mb-px border px-3.5 py-2.25 text-[12.5px] whitespace-nowrap transition ${
        disabled ? "cursor-not-allowed" : "cursor-pointer"
      } ${active ? "border-brand bg-brand font-bold text-on-brand" : "border-panel-border font-medium text-soft hover:border-brand"}`}
    >
      {children}
    </button>
  );
}
