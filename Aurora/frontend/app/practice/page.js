"use client";

import { useEffect, useRef, useState } from "react";
import AppSidebar from "@/components/AppSidebar";
import SessionSetup from "@/components/SessionSetup";
import SessionControls from "@/components/SessionControls";
import StatsRow, { formatDuration } from "@/components/StatsRow";
import WaveformHero from "@/components/WaveformHero";
import ConversationView from "@/components/ConversationView";
import CorrectionsPanel from "@/components/CorrectionsPanel";
import LatencyBadge from "@/components/LatencyBadge";
import { endSession, getOptions, startSession, streamMessage } from "@/lib/api";
import { getStoredUser, onUserUpdated, updateProfile } from "@/lib/auth";
import { getCompanion } from "@/lib/characters";
import { createAudioQueue } from "@/lib/audioQueue";
import AuthGuard from "@/components/AuthGuard";

let nextMessageId = 1;

export default function PracticePage() {
  return (
    <AuthGuard>
      <Practice />
    </AuthGuard>
  );
}

function Practice() {
  const [options, setOptions] = useState(null);
  const [setupValue, setSetupValue] = useState({ voice: "amy", style: "standard", scenario: "casual" });
  const [starting, setStarting] = useState(false);
  const [session, setSession] = useState(null); // { conversationId }
  // True once "End session" is clicked. `session` itself stays set (rather
  // than being nulled) so the just-finished transcript, stats and
  // corrections stay on screen as a recap — see handleEndSession.
  const [sessionEnded, setSessionEnded] = useState(false);
  const [messages, setMessages] = useState([]);
  const [turns, setTurns] = useState(0);
  const [sessionSeconds, setSessionSeconds] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [paused, setPaused] = useState(false);
  const [micAnalyser, setMicAnalyser] = useState(null);
  const [timings, setTimings] = useState(null);
  const [correctionsRefreshKey, setCorrectionsRefreshKey] = useState(0);
  const [correctionsCount, setCorrectionsCount] = useState(0);
  const [error, setError] = useState(null);
  const [playbackAnalyser, setPlaybackAnalyser] = useState(null);
  const [user, setUser] = useState(null);

  const audioQueueRef = useRef(null);
  const currentAuraMessageIdRef = useRef(null);
  const endCorrectionsTimeoutRef = useRef(null);

  // Cancel any pending catch-up corrections poll (see handleEndSession) on unmount.
  useEffect(() => () => clearTimeout(endCorrectionsTimeoutRef.current), []);

  // For the user's own chat bubbles (their avatar, WhatsApp-style). Read
  // after mount (localStorage is client-only) and stay in sync with edits
  // made elsewhere, e.g. a new photo uploaded on /profile in another tab.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is client-only; reading it during render would mismatch SSR output
    setUser(getStoredUser());
    return onUserUpdated(setUser);
  }, []);

  // Load the available voice/style/scenario options on mount. Identity now
  // comes from the auth token, so there's no local user id to read.
  useEffect(() => {
    getOptions()
      .then((opts) => {
        setOptions(opts);
        // Start from the companion/style saved on the profile when they're
        // still valid options; otherwise fall back to the server defaults.
        const saved = getStoredUser();
        const valid = (list, id, fallback) => (list.some((x) => x.id === id) ? id : fallback);
        setSetupValue({
          voice: valid(opts.voices, saved?.preferred_voice, opts.defaults.voice),
          style: valid(opts.styles, saved?.preferred_style, opts.defaults.style),
          scenario: opts.defaults.scenario,
        });
      })
      .catch(() => setError("Could not reach the AURA backend. Is it running on port 8000?"));
  }, []);

  // Session timer. Stops (without resetting) the moment the session ends, so
  // the recap shows the elapsed time the conversation actually ran for.
  useEffect(() => {
    if (!session || sessionEnded) return;
    const start = Date.now();
    const id = setInterval(() => setSessionSeconds((Date.now() - start) / 1000), 1000);
    return () => clearInterval(id);
  }, [session, sessionEnded]);

  function getAudioQueue() {
    if (!audioQueueRef.current) {
      const queue = createAudioQueue({
        onChunkStart: () => setIsPlaying(true),
        onQueueEmpty: () => setIsPlaying(false),
      });
      audioQueueRef.current = queue;
      // The analyser is created once per queue and reused for every chunk,
      // so this is a one-time state set, not a per-render ref read.
      setPlaybackAnalyser(queue.analyser);
    }
    return audioQueueRef.current;
  }

  // Picking a companion or style also saves it as the profile preference, so
  // it is the default next time and shows in the sidebar. Fire-and-forget: a
  // failed save shouldn't block starting a session.
  function handleSetupChange(next) {
    const voiceChanged = next.voice !== setupValue.voice;
    const styleChanged = next.style !== setupValue.style;
    setSetupValue(next);
    if (voiceChanged || styleChanged) {
      updateProfile({
        preferredVoice: voiceChanged ? next.voice : undefined,
        preferredStyle: styleChanged ? next.style : undefined,
      }).catch(() => {});
    }
  }

  /**
   * Returns the active session, creating one on demand if none exists yet.
   * Used both by the explicit "Start Session" button AND by the first
   * recording — holding the mic is enough to begin, no separate gate.
   *
   * If the previous session ended, its conversation is already closed
   * server-side, so this always opens a fresh one. That's also the one
   * moment the on-screen recap actually clears — not when the old session
   * ended, but when a new one genuinely begins.
   */
  async function ensureSession() {
    if (session && !sessionEnded) return session;

    clearTimeout(endCorrectionsTimeoutRef.current);
    const data = await startSession(setupValue);
    const newSession = { conversationId: data.conversation_id };
    setSession(newSession);
    setSessionEnded(false);
    setMessages([]);
    setTurns(0);
    setSessionSeconds(0);
    setTimings(null);
    setCorrectionsCount(0);
    setCorrectionsRefreshKey(0);
    setError(null);
    getAudioQueue(); // created during a user gesture, for browser autoplay policies
    return newSession;
  }

  async function handleStart() {
    setStarting(true);
    setError(null);
    try {
      await ensureSession();
    } catch (err) {
      setError(`Could not start session: ${err.message}`);
    } finally {
      setStarting(false);
    }
  }

  function handleEndSession() {
    // Tell the server the session is over so it gets an ended_at/duration in
    // history. Fire-and-forget: failing to close it server-side shouldn't
    // block the user from starting a fresh session locally.
    if (session) {
      endSession(session.conversationId).catch(() => {});
    }
    audioQueueRef.current?.close();
    audioQueueRef.current = null;
    setPlaybackAnalyser(null);
    setPaused(false);
    setSessionEnded(true);
    // The last turn's grammar/vocab analysis runs in the background and can
    // still be in flight when its one-shot poll fires. Poll again now, and
    // once more after a few seconds, so a slow analysis still makes it into
    // the recap instead of the count freezing one short.
    if (session) {
      setCorrectionsRefreshKey((k) => k + 1);
      clearTimeout(endCorrectionsTimeoutRef.current);
      endCorrectionsTimeoutRef.current = setTimeout(() => {
        setCorrectionsRefreshKey((k) => k + 1);
      }, 5000);
    }
    // Deliberately NOT clearing messages/turns/sessionSeconds/timings/
    // correctionsCount here. The finished conversation stays on screen as a
    // recap — with a "Start new session" action — instead of the dashboard
    // reverting to looking like nothing happened. ensureSession() clears it
    // once a new session actually starts.
  }

  function handleTogglePause() {
    const queue = audioQueueRef.current;
    if (!queue) return;
    if (paused) {
      queue.resume();
      setPaused(false);
    } else {
      queue.pause();
      setPaused(true);
    }
  }

  async function handleRecordingComplete(blob, recordingError) {
    if (recordingError) {
      setError(describeMicError(recordingError));
      return;
    }
    if (!blob) return;

    setError(null);
    setIsProcessing(true);
    currentAuraMessageIdRef.current = null;

    try {
      // Holding the mic is enough to start a session — no separate button required.
      const activeSession = await ensureSession();

      await streamMessage(activeSession.conversationId, blob, {
        onTranscript: (text) => {
          setMessages((prev) => [
            ...prev,
            { id: nextMessageId++, role: "user", text, timestamp: nowLabel() },
          ]);
        },
        onAudioChunk: (chunk) => {
          getAudioQueue().enqueue(chunk.data, chunk.text);
          setMessages((prev) => {
            if (currentAuraMessageIdRef.current == null) {
              const id = nextMessageId++;
              currentAuraMessageIdRef.current = id;
              return [...prev, { id, role: "assistant", text: chunk.text, pending: true }];
            }
            return prev.map((m) =>
              m.id === currentAuraMessageIdRef.current
                ? { ...m, text: `${m.text} ${chunk.text}` }
                : m
            );
          });
        },
        onDone: (payload) => {
          setTimings(payload.timings);
          setTurns((t) => t + 1);
          setMessages((prev) => {
            // Normally an assistant bubble already exists from onAudioChunk.
            // But if every sentence in this turn failed TTS synthesis (the
            // backend tolerates that and still sends `done` with the full
            // text), no audio_chunk ever arrived to create one — fall back
            // to adding the reply directly so it's never silently dropped.
            if (currentAuraMessageIdRef.current == null) {
              if (!payload.full_reply) return prev;
              return [
                ...prev,
                {
                  id: nextMessageId++,
                  role: "assistant",
                  text: payload.full_reply,
                  timestamp: nowLabel(),
                },
              ];
            }
            return prev.map((m) =>
              m.id === currentAuraMessageIdRef.current
                ? { ...m, text: payload.full_reply || m.text, pending: false, timestamp: nowLabel() }
                : m
            );
          });
          currentAuraMessageIdRef.current = null;
          setCorrectionsRefreshKey((k) => k + 1);
          setIsProcessing(false);
        },
        onError: (message) => {
          setError(message);
          setIsProcessing(false);
        },
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsProcessing(false);
    }
  }

  const sessionActive = Boolean(session) && !sessionEnded;

  // Single source of truth for the session status badge + controls, shared
  // between SessionControls and WaveformHero so they never disagree.
  let phase = "idle";
  if (sessionActive) {
    if (micAnalyser) phase = "recording";
    else if (isProcessing) phase = "thinking";
    else if (paused) phase = "paused";
    else if (isPlaying) phase = "speaking";
    else phase = "active";
  } else if (session && sessionEnded) {
    phase = "ended";
  }
  const canPause = phase === "speaking" || phase === "paused";

  const companion = getCompanion(setupValue.voice);
  const scenarioLabel = options?.scenarios.find((x) => x.id === setupValue.scenario)?.label;
  const awaitingReply = isProcessing && !messages.some((m) => m.pending);

  return (
    <div className="flex min-h-screen flex-1 flex-col lg:flex-row">
      <AppSidebar />

      <main className="min-w-0 flex-1 px-5 py-6 sm:px-8 sm:py-8 lg:px-10 lg:pt-9 lg:pb-14">
        <header className="flex flex-wrap items-end justify-between gap-4.5">
          <div>
            <div className="text-[10px] font-bold tracking-[0.22em] text-soft uppercase">Session</div>
            <h1 className="mt-2.5 font-display text-[clamp(30px,3.6vw,46px)] leading-none font-bold">Practise English</h1>
          </div>
          <SessionControls
            phase={phase}
            starting={starting}
            canPause={canPause}
            onStart={handleStart}
            onTogglePause={handleTogglePause}
            onEnd={handleEndSession}
          />
        </header>

        {error && (
          <div role="alert" className="mt-5 border border-brand bg-brand-soft px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {phase === "ended" && (
          <div className="mt-5 border border-brand bg-brand-soft px-4.5 py-3.5 text-sm">
            <strong className="font-bold">Session complete.</strong>{" "}
            {turns} {turns === 1 ? "turn" : "turns"} · {formatDuration(sessionSeconds)} ·{" "}
            {correctionsCount} {correctionsCount === 1 ? "correction" : "corrections"} — saved to your history.
            Ready when you are — hold the mic or use &ldquo;Start new session&rdquo; above.
          </div>
        )}

        <div className="mt-6.5 grid gap-5.5 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          <div className="flex min-w-0 flex-col gap-4.5">
            <WaveformHero
              companionId={companion.id}
              isProcessing={isProcessing}
              isPlaying={isPlaying}
              paused={paused}
              playbackAnalyser={playbackAnalyser}
              micAnalyser={micAnalyser}
              onAnalyser={setMicAnalyser}
              onRecordingComplete={handleRecordingComplete}
            />

            {timings && (
              <div className="flex justify-center">
                <LatencyBadge timings={timings} />
              </div>
            )}

            <StatsRow turns={turns} sessionSeconds={sessionSeconds} correctionsCount={correctionsCount} />

            <SessionSetup
              options={options}
              value={setupValue}
              onChange={handleSetupChange}
              sessionActive={sessionActive}
            />
          </div>

          <div className="flex min-w-0 flex-col gap-5.5">
            <ConversationView
              messages={messages}
              companionId={companion.id}
              thinking={awaitingReply}
              scenarioLabel={scenarioLabel}
              user={user}
            />
            <CorrectionsPanel
              key={session?.conversationId ?? "no-session"}
              conversationId={session?.conversationId}
              refreshKey={correctionsRefreshKey}
              onCountChange={setCorrectionsCount}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

function nowLabel() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function describeMicError(err) {
  switch (err?.name) {
    case "NotAllowedError":
      return "Microphone permission was denied or dismissed. Click the mic/lock icon in your browser's address bar, allow microphone access, then try again.";
    case "NotFoundError":
      return "No microphone was found. Check that one is connected and try again.";
    case "NotReadableError":
      return "Your microphone is already in use by another app. Close it and try again.";
    case "TooShortError":
      return "That was too short to send — hold the mic button down while you speak, then release.";
    default:
      return "Could not access the microphone. Check your browser's permission settings and try again.";
  }
}
