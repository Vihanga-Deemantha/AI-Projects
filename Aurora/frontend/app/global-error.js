"use client";

import "./globals.css";

/**
 * The last resort: it replaces the root layout when that layout itself fails, so it has to bring its own
 * <html> and <body> (and the stylesheet). The theme and fonts are set up by the layout that just broke,
 * so this page follows the system light/dark setting and uses the fallback serif.
 */
export default function GlobalError({ retry }) {
  return (
    <html lang="en">
      <body className="bg-background text-foreground">
        <main className="grid min-h-screen place-items-center px-5 py-16">
          <div role="alert" className="max-w-md text-center">
            <h1 className="font-display text-4xl leading-none font-bold">AURA couldn&apos;t load</h1>
            <p className="mt-4 text-[15px] leading-[1.6]">An unexpected error stopped the app from starting. Trying again often fixes it.</p>
            <button
              type="button"
              onClick={() => retry()}
              className="mt-8 inline-flex h-12 cursor-pointer items-center bg-foreground px-6.5 text-[11px] font-bold tracking-[0.18em] text-background uppercase"
            >
              Try again
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
