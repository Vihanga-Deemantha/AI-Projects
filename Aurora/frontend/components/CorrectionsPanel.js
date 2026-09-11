"use client";

import { useEffect, useState } from "react";
import { getRecentCorrections } from "@/lib/api";

/**
 * Grammar/vocab feedback panel — the "Recent Voice Sessions" slot in the
 * reference design is replaced with this, since it's AURA's actual
 * differentiator rather than a session-history list.
 *
 * Polls after each turn (Option B — one-turn-delayed feedback, same pattern
 * as local_client.py's fetch_and_print_feedback / seen_correction_ids).
 */
/**
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
    <div className="flex h-full flex-col gap-3 rounded-2xl border border-panel-border bg-panel p-4">
      <p className="text-sm font-semibold text-foreground/70">Language Feedback</p>
      {items.length === 0 ? (
        <p className="text-sm text-foreground/40">
          Feedback on grammar and vocabulary will show up here after your first turn.
        </p>
      ) : (
        <div className="flex flex-col gap-3 overflow-y-auto">
          {items
            .slice()
            .reverse()
            .map((c) => (
              <CorrectionCard key={c.id} correction={c} />
            ))}
        </div>
      )}
    </div>
  );
}

function CorrectionCard({ correction }) {
  const isError = correction.is_error;
  return (
    <div
      className={`rounded-xl border p-3 text-sm ${
        isError ? "border-rose-500/25 bg-rose-500/10" : "border-sky-500/25 bg-sky-500/10"
      }`}
    >
      <p className={`mb-1 text-xs font-semibold uppercase tracking-wide ${isError ? "text-rose-500" : "text-sky-500"}`}>
        {correction.category} · {correction.subtype.replaceAll("_", " ")}
      </p>
      <p className="text-foreground/70">
        <span className="line-through decoration-rose-300">{correction.original}</span>
        {" → "}
        <span className="font-medium text-foreground">{correction.correction}</span>
      </p>
      <p className="mt-1 text-xs text-foreground/50">{correction.explanation}</p>
    </div>
  );
}
