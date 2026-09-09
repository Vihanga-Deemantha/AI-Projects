"use client";

import { useEffect, useRef } from "react";

/** Scrolling transcript — user/AURA bubbles, auto-scrolls to the latest turn. */
export default function ConversationView({ messages }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full flex-1 items-center justify-center rounded-2xl border border-dashed border-panel-border text-sm text-foreground/40">
        Your conversation will appear here once you start talking.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-1 flex-col gap-3 overflow-y-auto rounded-2xl border border-panel-border bg-panel p-4">
      {messages.map((m) => (
        <Bubble key={m.id} message={m} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

function Bubble({ message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex items-end gap-2 ${isUser ? "flex-row-reverse self-end" : "self-start"}`}>
      <Avatar isUser={isUser} />
      <div
        className={`max-w-sm rounded-2xl border px-4 py-2.5 text-sm shadow-sm ${
          isUser
            ? "rounded-br-sm border-brand bg-brand text-white"
            : "rounded-bl-sm border-indigo-200 bg-indigo-100 text-indigo-950"
        } ${message.pending ? "opacity-60" : ""}`}
      >
        <p>{message.text || (message.pending ? "…" : "")}</p>
        {message.timestamp && (
          <p className={`mt-1 text-[10px] ${isUser ? "text-white/70" : "text-foreground/40"}`}>
            {message.timestamp}
          </p>
        )}
      </div>
    </div>
  );
}

function Avatar({ isUser }) {
  return (
    <div
      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-white ${
        isUser ? "bg-violet-400" : "bg-brand"
      }`}
    >
      {isUser ? "You" : "A"}
    </div>
  );
}
