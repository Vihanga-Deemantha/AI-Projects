"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import AppSidebar from "@/components/AppSidebar";
import Sprite from "@/components/Sprite";
import UserAvatar from "@/components/UserAvatar";
import { CorrectionItem } from "@/components/CorrectionsPanel";
import { getSession } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { faceSrc, getCompanion, sceneLabel, spriteSrc, styleLabel } from "@/lib/characters";
import { formatDate, formatDuration } from "../page";

export default function SessionDetailPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-1 flex-col lg:flex-row">
        <AppSidebar />
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
  const [user, setUser] = useState(null);

  // Read after mount: localStorage isn't available during SSR, and reading
  // it during render would mismatch the server-rendered output on hydration.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is client-only; reading it during render would mismatch SSR output
    setUser(getStoredUser());
  }, []);

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

  const who = getCompanion(session?.voice);

  return (
    <main className="min-w-0 flex-1 px-5 py-7 sm:px-8 lg:px-10 lg:pt-9 lg:pb-14">
      <Link href="/history" className="text-[10px] font-bold tracking-[0.18em] text-soft uppercase transition hover:text-brand">
        &larr; Speech history
      </Link>

      {status === "loading" && <p className="mt-6 text-sm text-mute">Loading session…</p>}

      {status === "error" && (
        <div role="alert" className="mt-6 border border-brand bg-brand-soft px-4 py-3 text-sm">{error}</div>
      )}

      {status === "ready" && (
        <div className="mt-5 grid gap-5.5 lg:grid-cols-[minmax(0,0.7fr)_minmax(0,1.3fr)]">
          <div className="relative grid min-h-85 place-items-end justify-center overflow-hidden border border-panel-border bg-brand-soft px-6">
            <div className="absolute top-[10%] left-1/2 aspect-square w-[70%] -translate-x-1/2 rounded-full bg-panel opacity-50" />
            <div className="absolute inset-x-0 bottom-0 h-[16%] bg-brand opacity-[0.16]" />
            <div className="relative z-3 -mb-0.5 h-60 max-w-full" style={{ aspectRatio: "700 / 680" }}>
              <div className="absolute bottom-[-1%] left-[10%] h-3.5 w-[80%] rounded-full bg-foreground opacity-[0.16] blur-sm" />
              <Sprite src={spriteSrc(who.id, "idle")} alt={who.name} className="absolute inset-0" />
            </div>
            <div className="absolute inset-x-5 top-5 z-4">
              <div className="text-[9.5px] font-bold tracking-[0.2em] text-soft uppercase">
                {formatDate(session.started_at)} · with {who.name}
              </div>
              <h1 className="mt-2 font-display text-[28px] leading-[1.05] font-bold">
                {sceneLabel(session.scenario)} · {styleLabel(session.style)}
              </h1>
            </div>
          </div>

          <div className="flex min-w-0 flex-col gap-5.5">
            <div className="flex flex-wrap">
              <Figure n={session.turn_count} label="Turns" />
              <Figure n={session.correction_count} label="Corrections" />
              <Figure n={formatDuration(session.duration_seconds)} label="Length" />
              <Figure n={styleLabel(session.style)} label="Style" small />
            </div>

            <div className="border border-panel-border bg-panel">
              <div className="border-b border-panel-border px-5 py-3.75 text-[10px] font-bold tracking-[0.2em] text-soft uppercase">Transcript</div>
              {session.messages.length === 0 ? (
                <p className="px-5 py-8 text-center text-sm text-mute">This session has no turns recorded.</p>
              ) : (
                <div className="flex flex-col gap-4 p-5">
                  {session.messages.map((m) => (
                    <Turn key={m.id} message={m} who={who} user={user} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function Figure({ n, label, small }) {
  return (
    <div className="-mr-px -mb-px flex-[1_1_110px] border border-panel-border bg-panel p-4.5">
      <div className={`font-display leading-none ${small ? "truncate text-lg" : "text-[26px]"}`}>{n}</div>
      <div className="mt-1.5 text-[9.5px] font-bold tracking-[0.16em] text-soft uppercase">{label}</div>
    </div>
  );
}

function Turn({ message, who, user }) {
  const isUser = message.role === "user";
  return (
    <div>
      <div className={`flex items-end gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}>
        {isUser ? (
          <UserAvatar user={user} className="h-8.5 w-8.5 flex-none text-[13px]" />
        ) : (
          <div
            role="img"
            aria-label={who.name}
            className="h-8.5 w-8.5 flex-none rounded-full bg-brand-soft bg-cover bg-top"
            style={{ backgroundImage: `url('${faceSrc(who.id, "neutral")}')` }}
          />
        )}
        <div className={`max-w-[76%] px-4.25 py-3.25 text-[14.5px] leading-[1.55] ${isUser ? "bg-brand-soft" : "bg-field"}`}>
          {message.content}
        </div>
      </div>

      {message.corrections.length > 0 && (
        <div className="mt-2 ml-11.5 border border-panel-border bg-background md:mr-11.5">
          {message.corrections.map((c) => (
            <CorrectionItem key={c.id} correction={c} />
          ))}
        </div>
      )}
    </div>
  );
}
