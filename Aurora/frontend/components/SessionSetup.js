"use client";

/**
 * Voice / style / scenario picker, sourced from GET /api/config/options
 * (backend/routers/config.py) so this never hand-duplicates personalities.py.
 *
 * Pre-session: full picker (starting the session itself is handled by
 * SessionControls — you can pick options here first, or just hold the mic
 * and start talking with the current selection / defaults).
 * In-session: collapses to a compact read-only summary bar.
 */
export default function SessionSetup({ options, value, onChange, sessionActive }) {
  if (!options) {
    return (
      <div className="rounded-2xl border border-panel-border bg-panel p-5 text-sm text-foreground/50">
        Loading session options…
      </div>
    );
  }

  if (sessionActive) {
    const voice = options.voices.find((v) => v.id === value.voice);
    const style = options.styles.find((s) => s.id === value.style);
    const scenario = options.scenarios.find((s) => s.id === value.scenario);
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-panel-border bg-panel px-5 py-3 text-sm">
        <SummaryPill label="Voice" value={voice?.label} />
        <SummaryPill label="Style" value={style?.label} />
        <SummaryPill label="Scenario" value={scenario?.label} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 rounded-2xl border border-panel-border bg-panel p-5">
      <Picker
        title="Voice"
        items={options.voices}
        selected={value.voice}
        onSelect={(id) => onChange({ ...value, voice: id })}
        renderExtra={(item) => item.desc}
      />
      <Picker
        title="Speaking Style"
        items={options.styles}
        selected={value.style}
        onSelect={(id) => onChange({ ...value, style: id })}
      />
      <Picker
        title="Scenario"
        items={options.scenarios}
        selected={value.scenario}
        onSelect={(id) => onChange({ ...value, scenario: id })}
      />
    </div>
  );
}

function Picker({ title, items, selected, onSelect, renderExtra }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-foreground/40">{title}</p>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => {
          const active = item.id === selected;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.id)}
              className={`rounded-xl border px-3 py-2 text-left text-sm transition ${
                active
                  ? "border-brand bg-brand/10 text-brand"
                  : "border-panel-border text-foreground/70 hover:border-brand/30"
              }`}
            >
              <span className="font-medium">{item.label}</span>
              {renderExtra && (
                <span className="ml-1 text-xs text-foreground/40">{renderExtra(item)}</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SummaryPill({ label, value }) {
  return (
    <span className="rounded-full bg-brand/10 px-3 py-1 text-xs font-medium text-brand">
      {label}: {value || "—"}
    </span>
  );
}
