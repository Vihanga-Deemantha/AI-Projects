"use client";

import { useEffect, useRef } from "react";
import { faceSrc, getCompanion } from "@/lib/characters";

/**
 * Scrolling transcript — the companion's bubbles carry their headshot, yours
 * are accent-marked on the right. Auto-scrolls its OWN container to the latest
 * turn (not the page, which scrollIntoView would also yank around).
 */
export default function ConversationView({ messages, companionId, thinking, scenarioLabel }) {
  const scrollRef = useRef(null);
  const companion = getCompanion(companionId);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);

  return (
    <div className="flex flex-col border border-panel-border bg-panel">
      <div className="flex items-center justify-between gap-3.5 border-b border-panel-border px-5 py-3.75">
        <span className="text-[10px] font-bold tracking-[0.2em] text-soft uppercase">Conversation</span>
        {scenarioLabel && <span className="truncate text-[10px] font-bold tracking-[0.16em] text-mute uppercase">{scenarioLabel}</span>}
      </div>

      {messages.length === 0 && !thinking ? (
        <div className="grid min-h-50 place-items-center px-6 py-10 text-center text-sm text-mute">
          Your conversation with {companion.name} will appear here once you start talking.
        </div>
      ) : (
        <div ref={scrollRef} className="flex max-h-115 min-h-50 flex-col gap-4 overflow-y-auto p-5">
          {messages.map((m) => (
            <Bubble key={m.id} message={m} companion={companion} />
          ))}
          {thinking && (
            <div className="flex items-end gap-2.5">
              <Face id={companion.id} name={companion.name} expr="neutral" />
              <div className="flex items-center gap-1.25 bg-field px-4.5 py-4" aria-label={`${companion.name} is thinking`}>
                {[0, 0.15, 0.3].map((delay) => (
                  <span
                    key={delay}
                    className="h-1.5 w-1.5 rounded-full bg-brand"
                    style={{ animation: `aura-float 1s ease-in-out ${delay}s infinite` }}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Bubble({ message, companion }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex items-end gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}>
      {isUser ? (
        <div className="h-8.5 w-8.5 flex-none rounded-full bg-brand" aria-label="You" />
      ) : (
        <Face id={companion.id} name={companion.name} expr={message.pending ? "speaking" : "neutral"} />
      )}
      <div
        className={`relative max-w-[76%] px-4.25 pt-3.25 pb-5.5 text-[14.5px] leading-[1.55] ${
          isUser ? "bg-brand-soft" : "bg-field"
        } ${message.pending ? "opacity-70" : ""}`}
      >
        {message.text || (message.pending ? "…" : "")}
        {message.timestamp && (
          <span className="absolute right-3 bottom-1.5 text-[10px] text-soft">{message.timestamp}</span>
        )}
      </div>
    </div>
  );
}

function Face({ id, name, expr }) {
  return (
    <div
      role="img"
      aria-label={name}
      className="h-8.5 w-8.5 flex-none rounded-full bg-brand-soft bg-cover bg-top"
      style={{ backgroundImage: `url('${faceSrc(id, expr)}')` }}
    />
  );
}
