/** Shown inside the sidebar frame while a signed-in page is being fetched, so a click gets an answer at once. */
export default function Loading() {
  return (
    <main className="grid min-w-0 flex-1 place-items-center px-5 py-16">
      <div role="status" className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-panel-border border-t-brand motion-reduce:animate-none" aria-hidden="true" />
        <p className="text-sm text-mute">Loading…</p>
      </div>
    </main>
  );
}
