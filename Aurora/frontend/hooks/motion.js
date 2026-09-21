"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

const REDUCED_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReduced(cb) {
  const mq = window.matchMedia(REDUCED_QUERY);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

/** True when the user asked the OS for reduced motion. Server render assumes motion is fine. */
export function usePrefersReducedMotion() {
  return useSyncExternalStore(
    subscribeReduced,
    () => window.matchMedia(REDUCED_QUERY).matches,
    () => false
  );
}

/**
 * Publishes the pointer position, normalised to -1..1 across the viewport, as
 * the CSS variables --px / --py on <html>. Figures read them in `calc()`, so
 * the whole page can lean toward the cursor without a single React re-render.
 */
export function usePointerVars(enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const root = document.documentElement;
    let raf = 0;
    const onMove = (e) => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const x = (e.clientX / (window.innerWidth || 1)) * 2 - 1;
        const y = (e.clientY / (window.innerHeight || 1)) * 2 - 1;
        root.style.setProperty("--px", Math.max(-1, Math.min(1, x)).toFixed(3));
        root.style.setProperty("--py", Math.max(-1, Math.min(1, y)).toFixed(3));
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      if (raf) cancelAnimationFrame(raf);
      root.style.removeProperty("--px");
      root.style.removeProperty("--py");
    };
  }, [enabled]);
}

/**
 * Scroll parallax for DECORATIVE layers only: any element with
 * data-par="0.2" drifts by that fraction of its distance from viewport
 * centre. Content never depends on it.
 */
export function useParallax(enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    let raf = 0;
    const update = () => {
      raf = 0;
      const vh = window.innerHeight || 800;
      document.querySelectorAll("[data-par]").forEach((node) => {
        const f = parseFloat(node.getAttribute("data-par")) || 0;
        const r = node.parentElement.getBoundingClientRect();
        node.style.transform = `translate3d(0,${((r.top + r.height / 2 - vh / 2) * -f).toFixed(1)}px,0)`;
      });
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    document.addEventListener("scroll", onScroll, true);
    update();
    return () => {
      document.removeEventListener("scroll", onScroll, true);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [enabled]);
}

/** A counter that increments every `intervalMs` while `enabled`; returns [tick, setTick]. */
export function useTicker(intervalMs, enabled = true) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => setTick((n) => n + 1), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs, enabled]);
  return [tick, setTick];
}
