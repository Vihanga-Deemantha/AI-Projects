"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import SessionReportView from "@/components/SessionReportView";
import { getSession } from "@/lib/api";
import { formatDate } from "@/lib/format";

export default function Report() {
  const { id } = useParams();
  const [session, setSession] = useState(null);

  // Session details (scenario, style, voice, date) frame the report; it still
  // renders without them if that call fails.
  useEffect(() => {
    let cancelled = false;
    getSession(id)
      .then((s) => !cancelled && setSession(s))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <main className="min-w-0 flex-1 px-5 py-7 sm:px-8 lg:px-10 lg:pt-9 lg:pb-14">
      <div className="max-w-205">
        <Link href={`/history/${id}`} className="text-[10px] font-bold tracking-[0.18em] text-soft uppercase transition hover:text-brand">
          &larr; Transcript
        </Link>
        <header className="mt-5">
          <div className="text-[10px] font-bold tracking-[0.22em] text-soft uppercase">
            Session report{session ? ` · ${formatDate(session.started_at)}` : ""}
          </div>
          <h1 className="mt-2.5 font-display text-[clamp(30px,3.6vw,46px)] leading-none font-bold">How that went</h1>
        </header>
        <SessionReportView conversationId={id} session={session} />
      </div>
    </main>
  );
}
