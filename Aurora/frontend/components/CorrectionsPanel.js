"use client";

import { useEffect, useState } from "react";
import { getRecentCorrections } from "@/lib/api";

/**
 * Grammar/vocab feedback panel — AURA's actual differentiator. Each item
 * shows what you said struck through, the better form, and why.
 *
 * Polls after each turn (one-turn-delayed feedback, same pattern as
 * local_client.py's fetch_and_print_feedback / seen_correction_ids).
 *
 * IMPORTANT: render this with `key={conversationId}` from the parent. That
 * makes React remount a fresh instance (and fresh `items` state) whenever
 * the conversation changes, instead of carrying corrections over from a
 * previous, now-ended conversation — the React-recommended way to reset
 * state on a prop change, rather than doing it via an effect.
 */
export default function CorrectionsPanel({ conversationId, refreshKey, onCountChange }) {
  const [items, setItems] = useState([]);

  useEffect(() => {
    if (!conversationId || !refreshKey) return;
    let cancelled = false;

    getRecentCorrections(conversationId, 10)
      .then(({ corrections }) => {
        if (cancelled) return;
        // Dedup by reading existing ids directly from the array being updated,
        // in one pure setState call. (Previously this nested a setItems call
        // inside a setSeenIds updater — React's Strict Mode deliberately
        // double-invokes updater functions in dev to catch exactly that kind
        // of impurity, which was duplicating every correction.)
        setItems((prevItems) => {
          const existingIds = new Set(prevItems.map((c) => c.id));
          const fresh = corrections.filter((c) => !existingIds.has(c.id));
          return fresh.length > 0 ? [...prevItems, ...fresh] : prevItems;
        });
      })
      .catch(() => {
        /* Silently ignore polling errors, same as the terminal client. */
      });

    return () => {
      cancelled = true;
    };
  }, [conversationId, refreshKey]);

  useEffect(() => {
    onCountChange?.(items.length);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.length]);

  return (
    <div className="border border-panel-border bg-panel">
      <div className="flex items-center justify-between gap-3 border-b border-panel-border px-5 py-3.75">
        <span className="text-[10px] font-bold tracking-[0.2em] text-brand uppercase">Corrections</span>
        <span className="text-[10px] font-bold tracking-[0.16em] text-mute uppercase">{items.length} this session</span>
      </div>
      {items.length === 0 ? (
        <p className="px-5 py-6 text-sm leading-normal text-mute">
          Feedback on grammar and vocabulary will show up here after your first turn.
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

export function CorrectionItem({ correction }) {
  const isError = correction.is_error;
  return (
    <div className="border-b border-panel-border px-5 py-4.5 last:border-b-0">
      <div className="mb-2 text-[9.5px] font-bold tracking-[0.16em] text-mute uppercase">
        {isError ? "" : "Suggestion · "}
        {correction.category} · {correction.subtype.replaceAll("_", " ")}
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
