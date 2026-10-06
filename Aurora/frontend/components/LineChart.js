"use client";

import { useRef, useState } from "react";

const W = 640;
const H = 260;
const M = { top: 12, right: 14, bottom: 30, left: 34 };
const PLOT_W = W - M.left - M.right;
const PLOT_H = H - M.top - M.bottom;
const GRID = [0, 25, 50, 75, 100];

/**
 * A small dependency-free line chart for 0-100 scores over time.
 *
 * `labels`: one x label per point (e.g. "Oct 5").
 * `series`: [{ key, label, color, values: (number | null)[], bold? }] — a null is a
 * week with no data and BREAKS the line (an empty week isn't a score of zero).
 *
 * Hover (or tap) anywhere on the chart to read the values for that week.
 */
export default function LineChart({ labels, series }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null); // index of the highlighted point

  const count = labels.length;
  const x = (i) => M.left + (count === 1 ? PLOT_W / 2 : (i / (count - 1)) * PLOT_W);
  const y = (v) => M.top + PLOT_H - (v / 100) * PLOT_H;
  const labelEvery = Math.max(1, Math.ceil(count / 8));

  function onMove(e) {
    const rect = svgRef.current.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((px - M.left) / PLOT_W) * (count - 1));
    setHover(Math.max(0, Math.min(count - 1, i)));
  }

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full touch-none select-none"
        role="img"
        aria-label={`Score trend: ${series.map((s) => s.label).join(", ")}`}
        onPointerMove={onMove}
        onPointerDown={onMove}
        onPointerLeave={() => setHover(null)}
      >
        {/* grid + y axis */}
        {GRID.map((g) => (
          <g key={g}>
            <line x1={M.left} x2={W - M.right} y1={y(g)} y2={y(g)} stroke="var(--panel-border)" strokeWidth="1" />
            <text x={M.left - 8} y={y(g) + 3.5} textAnchor="end" fontSize="10" fill="var(--mute)">
              {g}
            </text>
          </g>
        ))}

        {/* x labels */}
        {labels.map((label, i) =>
          i % labelEvery === 0 || i === count - 1 ? (
            <text key={`${label}-${i}`} x={x(i)} y={H - 9} textAnchor="middle" fontSize="10" fill="var(--mute)">
              {label}
            </text>
          ) : null
        )}

        {/* hover guide */}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={M.top + PLOT_H} stroke="var(--mute)" strokeWidth="1" strokeDasharray="3 3" />}

        {/* lines */}
        {series.map((s) => (
          <g key={s.key}>
            {segments(s.values).map((seg, k) => (
              <polyline
                key={k}
                points={seg.map(({ i, v }) => `${x(i)},${y(v)}`).join(" ")}
                fill="none"
                stroke={s.color}
                strokeWidth={s.bold ? 3 : 2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            ))}
            {s.values.map((v, i) =>
              v == null ? null : (
                <rect
                  key={i}
                  x={x(i) - (hover === i ? 4 : 3)}
                  y={y(v) - (hover === i ? 4 : 3)}
                  width={hover === i ? 8 : 6}
                  height={hover === i ? 8 : 6}
                  fill={s.color}
                />
              )
            )}
          </g>
        ))}
      </svg>

      {hover != null && (
        <div
          className="pointer-events-none absolute top-2 border border-panel-border bg-panel px-3 py-2 text-xs shadow-md"
          style={{ left: `${Math.min(78, Math.max(2, (x(hover) / W) * 100 - 8))}%` }}
        >
          <div className="mb-1 font-bold">{labels[hover]}</div>
          {series.map((s) => (
            <div key={s.key} className="flex items-center gap-2">
              <span className="h-2 w-2" style={{ background: s.color }} />
              <span className="text-soft">{s.label}</span>
              <span className="ml-auto pl-3 font-bold">{s.values[hover] ?? "—"}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Splits a series into runs of consecutive non-null values, so gaps stay gaps. */
function segments(values) {
  const out = [];
  let run = [];
  values.forEach((v, i) => {
    if (v == null) {
      if (run.length) out.push(run);
      run = [];
    } else {
      run.push({ i, v });
    }
  });
  if (run.length) out.push(run);
  // A lone point has no line to draw; its square marker is enough.
  return out.filter((r) => r.length > 1);
}
