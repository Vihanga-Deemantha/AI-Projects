import Link from "next/link";

/** The page for an address that matches nothing, in the app's own look rather than the framework's default. */
export default function NotFound() {
  return (
    <main className="grid min-h-screen flex-1 place-items-center px-5 py-16">
      <div className="max-w-md text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center bg-brand font-display text-2xl font-bold text-on-brand" aria-hidden="true">A</div>
        <p className="mt-6 text-[10px] font-bold tracking-[0.22em] text-soft uppercase">Error 404</p>
        <h1 className="mt-3 font-display text-4xl leading-none font-bold">That page isn&apos;t here</h1>
        <p className="mt-4 text-[15px] leading-[1.6] text-soft">The address may be mistyped, or the page may have moved.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            href="/"
            className="inline-flex h-12 items-center bg-foreground px-6.5 text-[11px] font-bold tracking-[0.18em] text-background uppercase transition hover:bg-brand hover:text-on-brand"
          >
            Back to AURA
          </Link>
          <Link
            href="/practice"
            className="inline-flex h-12 items-center border border-panel-border px-6.5 text-[11px] font-bold tracking-[0.18em] text-soft uppercase transition hover:border-brand hover:text-brand"
          >
            Go to practice
          </Link>
        </div>
      </div>
    </main>
  );
}
