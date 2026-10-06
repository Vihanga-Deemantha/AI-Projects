"use client";

import Link from "next/link";
import { useEffect } from "react";

/**
 * What a learner sees when a page throws while rendering, instead of a blank screen. Next 16 hands the
 * boundary `retry`, which re-fetches and re-renders the page; the error itself goes to the console.
 */
export default function Error({ error, retry }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="grid min-h-screen flex-1 place-items-center px-5 py-16">
      <div role="alert" className="max-w-md text-center">
        <p className="text-[10px] font-bold tracking-[0.22em] text-soft uppercase">Something broke</p>
        <h1 className="mt-3 font-display text-4xl leading-none font-bold">This page hit an error</h1>
        <p className="mt-4 text-[15px] leading-[1.6] text-soft">An unexpected error stopped the page from loading. Trying again often fixes it.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <button
            type="button"
            onClick={() => retry()}
            className="inline-flex h-12 cursor-pointer items-center bg-foreground px-6.5 text-[11px] font-bold tracking-[0.18em] text-background uppercase transition hover:bg-brand hover:text-on-brand"
          >
            Try again
          </button>
          <Link
            href="/"
            className="inline-flex h-12 items-center border border-panel-border px-6.5 text-[11px] font-bold tracking-[0.18em] text-soft uppercase transition hover:border-brand hover:text-brand"
          >
            Back to AURA
          </Link>
        </div>
      </div>
    </main>
  );
}
