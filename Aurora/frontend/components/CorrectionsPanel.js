"use client";

import { useEffect, useState } from "react";
import { getRecentCorrections } from "@/lib/api";

// Analysis of a turn takes a couple of seconds and runs while the coach is
// still speaking, so the first look is often already complete. When it isn't,
// the server says so (`pending`) and we look again — but only then, and never
// for longer than MAX_POLL_MS (a stuck analysis must not poll forever).
const POLL_INTERVAL_MS = 1500;
const MAX_POLL_MS = 30_000;

/**
 * Grammar/vocab feedback panel — AURA's actual differentiator. Each item
 * shows what you said struck through, the better form, and why.
 *
 * Re-fetches whenever `refreshKey` changes (after each turn, and when the
 * session ends) and keeps polling while the server reports turns that are
 * still being analysed.
 *
 * IMPORTANT: render this with `key={conversationId}` from the parent. That
 * makes React remount a fresh instance (and fresh `items` state) whenever
 * the conversation changes, instead of carrying corrections over from a
 * previous, now-ended conversation — the React-recommended way to reset
 * state on a prop change, rather than doing it via an effect.
 */
export default function CorrectionsPanel({ conversationId, refreshKey, onCountChange }) {
  const [items, setItems] = useState([]);
  const [analysing, setAnalysing] = useState(false);

  useEffect(() => {
    if (!conversationId || !refreshKey) return;
    let cancelled = false;
    let timer = null;
    const startedAt = Date.now();

    async function poll() {
      try {
        const { corrections, pending } = await getRecentCorrections(conversationId, 20);
        if (cancelled) return;
        // Dedup by reading existing ids directly from the array being updated,
        // in one pure setState call (Strict Mode double-invokes updaters in dev).
        setItems((prevItems) => {
          const existingIds = new Set(prevItems.map((c) => c.id));
          const fresh = corrections.filter((c) => !existingIds.has(c.id));
          return fresh.length > 0 ? [...prevItems, ...fresh] : prevItems;
        });
        const keepWaiting = pending > 0 && Date.now() - startedAt < MAX_POLL_MS;
        setAnalysing(keepWaiting);
        if (keepWaiting) timer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch {
        /* Silently stop on polling errors, same as the terminal client. */
        if (!cancelled) setAnalysing(false);
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [conversationId, refreshKey]);

  // Praise ("nice idiom!") isn't a correction, so it doesn't count as one.
  const fixes = items.filter((c) => !c.is_positive).length;
  const praise = items.length - fixes;

  useEffect(() => {
    onCountChange?.(fixes);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fixes]);

  return (
    <div className="border border-panel-border bg-panel">
      <div className="flex items-center justify-between gap-3 border-b border-panel-border px-5 py-3.75">
        <span className="text-[10px] font-bold tracking-[0.2em] text-brand uppercase">Corrections</span>
        <span className="flex items-center gap-2 text-[10px] font-bold tracking-[0.16em] text-mute uppercase">
          {analysing && <span className="aura-blink h-1.5 w-1.5 bg-brand" aria-hidden="true" />}
          {analysing ? "Analysing…" : `${fixes} this session${praise > 0 ? ` · ${praise} nice` : ""}`}
        </span>
      </div>
      {items.length === 0 ? (
        <p className="px-5 py-6 text-sm leading-normal text-mute">
          {analysing
            ? "Checking what you just said…"
            : "Feedback on grammar and vocabulary will show up here after your first turn."}
        </p>
      ) : (
        <div className="max-h-105 overflow-y-auto">
          {items
            .slice()
            .reverse()
            .map((c) => (
              <CorrectionItem key={c.id} correction={c} />
            ))}
        </div>
      )}
    </div>
  );
}

/** One piece of feedback: a mistake, a suggestion, or praise for something done well. */
export function CorrectionItem({ correction }) {
  const label = correction.label || correction.subtype.replaceAll("_", " ");

  if (correction.is_positive) {
    return (
      <div className="border-b border-l-2 border-panel-border border-l-brand px-5 py-4.5 last:border-b-0">
        <div className="mb-2 text-[9.5px] font-bold tracking-[0.16em] text-brand uppercase">Nice · {label}</div>
        <div className="text-[14.5px] font-bold">&ldquo;{correction.original}&rdquo;</div>
        <div className="mt-1.75 text-[12.5px] leading-[1.55] text-soft">{correction.explanation}</div>
      </div>
    );
  }

  const isError = correction.is_error;
  return (
    <div className="border-b border-panel-border px-5 py-4.5 last:border-b-0">
      <div className="mb-2 text-[9.5px] font-bold tracking-[0.16em] text-mute uppercase">
        {isError ? "" : "Suggestion · "}
        {label}
      </div>
      <div className="flex flex-wrap items-center gap-2.25 text-[14.5px]">
        <span className="text-mute line-through">{correction.original}</span>
        <span className="text-brand">&rarr;</span>
        <span className="font-bold">{correction.correction}</span>
      </div>
      <div className="mt-1.75 text-[12.5px] leading-[1.55] text-soft">{correction.explanation}</div>
    </div>
  );
}
