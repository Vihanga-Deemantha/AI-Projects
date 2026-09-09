"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import NavBar from "@/components/NavBar";
import { getSession } from "@/lib/api";
import { formatDate, formatDuration } from "../page";

export default function SessionDetailPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-1 flex-col">
        <NavBar />
        <SessionDetail />
      </div>
    </AuthGuard>
  );
}

function SessionDetail() {
  const { id } = useParams();
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getSession(id)
      .then((d) => {
        if (cancelled) return;
        setSession(d);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-8">
      <Link href="/history" className="text-sm text-brand hover:underline">
        ← Back to history
      </Link>

      {status === "loading" && (
        <p className="mt-6 text-sm text-foreground/40">Loading session…</p>
      )}

      {status === "error" && (
        <div className="mt-6 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {status === "ready" && (
        <>
          <header className="mt-4 mb-6">
            <h1 className="text-2xl font-bold capitalize">
              {session.scenario} · {session.style}
            </h1>
            <p className="text-sm text-foreground/50">
              {formatDate(session.started_at)} · voice: {session.voice} ·{" "}
              {session.turn_count} turns · {session.correction_count} corrections ·{" "}
              {formatDuration(session.duration_seconds)}
            </p>
          </header>

          {session.messages.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-panel-border p-8 text-center text-sm text-foreground/40">
              This session has no turns recorded.
            </p>
          ) : (
            <div className="flex flex-col gap-4">
              {session.messages.map((m) => (
                <Turn key={m.id} message={m} />
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}

function Turn({ message }) {
  const isUser = message.role === "user";
  return (
    <div className={isUser ? "self-end text-right" : "self-start"}>
      <div
        className={`inline-block max-w-xl rounded-2xl border px-4 py-2.5 text-left text-sm ${
          isUser
            ? "rounded-br-sm border-brand bg-brand text-white"
            : "rounded-bl-sm border-indigo-200 bg-indigo-100 text-indigo-950"
        }`}
      >
        <p className={`mb-1 text-[10px] font-semibold uppercase tracking-wide ${isUser ? "text-white/60" : "text-indigo-500"}`}>
          {isUser ? "You" : "AURA"}
        </p>
        <p>{message.content}</p>
      </div>

      {message.corrections.length > 0 && (
        <div className="mt-2 flex flex-col gap-2 text-left">
          {message.corrections.map((c) => (
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
      className={`max-w-xl rounded-xl border p-3 text-sm ${
        isError ? "border-rose-100 bg-rose-50/60" : "border-sky-100 bg-sky-50/60"
      }`}
    >
      <p className={`mb-1 text-xs font-semibold uppercase tracking-wide ${isError ? "text-rose-600" : "text-sky-600"}`}>
        {isError ? "❌" : "💡"} {correction.category} · {correction.subtype.replaceAll("_", " ")}
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
