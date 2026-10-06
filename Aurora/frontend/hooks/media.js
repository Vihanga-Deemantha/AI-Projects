"use client";

import { useSyncExternalStore } from "react";

/**
 * True while the browser window matches a CSS media query, e.g. `useMediaQuery("(min-width: 1024px)")`.
 * The server cannot know, so it renders with `serverValue` and the browser corrects it on hydration.
 */
export function useMediaQuery(query, serverValue = false) {
  return useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia(query);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => serverValue
  );
}

/** Tailwind's `lg` breakpoint: where the sidebar stops being a drawer and becomes a fixed rail. */
export const DESKTOP_QUERY = "(min-width: 1024px)";
