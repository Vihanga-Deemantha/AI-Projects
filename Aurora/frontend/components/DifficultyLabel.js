const ARROWS = {
  up: { glyph: "↑", text: "moved up after your last session" },
  down: { glyph: "↓", text: "moved down after your last session" },
  same: { glyph: "→", text: "unchanged after your last session" },
};

/**
 * A difficulty level as the learner reads it: "Intermediate ↑". The arrow is where
 * their last session moved the automatic level, so it only shows for an automatic level
 * that has some history behind it; a level they pinned, or a new learner's default,
 * is just its name.
 *
 * `level` is GET /api/practice/difficulty (or any `{ label, trend?, mode?, recent_scores? }`).
 */
export default function DifficultyLabel({ level, className = "" }) {
  const arrow = level.mode === "auto" && level.recent_scores?.length ? ARROWS[level.trend] : null;
  return (
    <span className={className}>
      {level.label}
      {arrow && (
        <>
          {" "}
          <span aria-hidden="true" className={level.trend === "up" ? "text-brand" : undefined}>
            {arrow.glyph}
          </span>
          <span className="sr-only"> ({arrow.text})</span>
        </>
      )}
    </span>
  );
}
