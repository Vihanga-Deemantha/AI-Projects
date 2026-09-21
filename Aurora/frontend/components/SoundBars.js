/**
 * Decorative CSS soundwave (no audio involved) — used on the landing page and
 * in static previews. The real, analyser-driven bars are components/Waveform.js.
 */
export default function SoundBars({
  count = 26,
  barWidth = 5,
  wave = "sin",
  freq = 0.9,
  delayStep = 0.055,
  baseDuration = 1.05,
  className = "",
  barClassName = "bg-foreground",
}) {
  return (
    <div className={`flex items-end ${className}`} aria-hidden="true">
      {Array.from({ length: count }, (_, k) => {
        const w = wave === "cos" ? Math.cos(k * freq) : Math.sin(k * freq);
        return (
          <div
            key={k}
            className={barClassName}
            style={{
              width: `${barWidth}px`,
              height: `${(30 + Math.abs(w) * 70).toFixed(1)}%`,
              transformOrigin: "bottom",
              animation: `aura-bar ${(baseDuration + (k % 5) * 0.12).toFixed(2)}s ease-in-out ${(k * delayStep).toFixed(2)}s infinite`,
            }}
          />
        );
      })}
    </div>
  );
}
