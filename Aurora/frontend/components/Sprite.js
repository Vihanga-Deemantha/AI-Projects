"use client";

import { useState } from "react";

/** A single companion sprite, painted as a background so it never reflows or lazy-loads oddly. */
export default function Sprite({ src, alt, className = "", style }) {
  return (
    <div
      role="img"
      aria-label={alt}
      className={`pointer-events-none bg-contain bg-bottom bg-no-repeat select-none ${className}`}
      style={{ backgroundImage: `url('${src}')`, ...style }}
    />
  );
}

/**
 * Two stacked layers that ping-pong: when `src` changes, the new image is
 * written into the layer that is currently invisible, then the layers swap
 * opacity. The eye sees one pose dissolving into the next rather than a cut.
 *
 * The pool and the index that selects the active layer live in ONE state
 * object and change together, so a render can never pair the new image with
 * the old index and light the stale layer.
 */
export function SpriteCrossfade({ src, alt, className = "" }) {
  const [state, setState] = useState({ src, pool: [src, src], idx: 0 });

  // Derived-from-props update, done during render (React's recommended
  // pattern) rather than in an effect, so there is never a stale frame.
  if (state.src !== src) {
    const idx = state.idx + 1;
    const pool = state.pool.slice();
    pool[idx % 2] = src;
    setState({ src, pool, idx });
  }

  return (
    // No position class here on purpose: callers supply their own (`absolute
    // inset-0` or `relative h-full w-full`) and the two layers position
    // against it. Forcing `relative` would fight an `absolute` caller.
    <div role="img" aria-label={alt} className={className}>
      {[0, 1].map((i) => {
        const on = i === state.idx % 2;
        return (
          <div
            key={i}
            className="pointer-events-none absolute inset-0 bg-contain bg-bottom bg-no-repeat select-none"
            style={{
              backgroundImage: state.pool[i] ? `url('${state.pool[i]}')` : "none",
              opacity: on ? 1 : 0,
              transform: on ? "translateY(0) scale(1)" : "translateY(10px) scale(.986)",
              transition: "opacity .7s cubic-bezier(.4,0,.2,1), transform .85s cubic-bezier(.22,1,.36,1)",
              willChange: "opacity, transform",
            }}
          />
        );
      })}
    </div>
  );
}
