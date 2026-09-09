"use client";

import { useEffect, useRef, useState } from "react";
import NavBar from "@/components/NavBar";
import SessionSetup from "@/components/SessionSetup";
import SessionControls from "@/components/SessionControls";
import StatsRow from "@/components/StatsRow";
import WaveformHero from "@/components/WaveformHero";
import ConversationView from "@/components/ConversationView";
import CorrectionsPanel from "@/components/CorrectionsPanel";
import LatencyBadge from "@/components/LatencyBadge";
import { endSession, getOptions, startSession, streamMessage } from "@/lib/api";
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

  const audioQueueRef = useRef(null);
  const currentAuraMessageIdRef = useRef(null);

  // Load the available voice/style/scenario options on mount. Identity now
  // comes from the auth token, so there's no local user id to read.
  useEffect(() => {
    getOptions()
      .then((opts) => {
        setOptions(opts);
        setSetupValue({
          voice: opts.defaults.voice,
          style: opts.defaults.style,
          scenario: opts.defaults.scenario,
        });
      })
      .catch(() => setError("Could not reach the AURA backend. Is it running on port 8000?"));
  }, []);

  // Session timer.
  useEffect(() => {
    if (!session) return;
    const start = Date.now();
    const id = setInterval(() => setSessionSeconds((Date.now() - start) / 1000), 1000);
    return () => clearInterval(id);
  }, [session]);

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

  /**
   * Returns the active session, creating one on demand if none exists yet.
   * Used both by the explicit "Start Session" button AND by the first
   * recording — holding the mic is enough to begin, no separate gate.
   */
  async function ensureSession() {
    if (session) return session;
    const data = await startSession(setupValue);
    const newSession = { conversationId: data.conversation_id };
    setSession(newSession);
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
    setSession(null);
    setMessages([]);
    setTurns(0);
    setSessionSeconds(0);
    setTimings(null);
    setCorrectionsCount(0);
    setCorrectionsRefreshKey(0);
    setError(null);
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

  const sessionActive = Boolean(session);

  // Single source of truth for the session status badge + controls, shared
  // between SessionControls and WaveformHero so they never disagree.
  let phase = "idle";
  if (sessionActive) {
    if (micAnalyser) phase = "recording";
    else if (isProcessing) phase = "thinking";
    else if (paused) phase = "paused";
    else if (isPlaying) phase = "speaking";
    else phase = "active";
  }
  const canPause = phase === "speaking" || phase === "paused";

  return (
    <div className="flex min-h-screen flex-1 flex-col">
      <NavBar />

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-8 py-8">
        <header>
          <h1 className="text-2xl font-bold">AI Speaking Coach</h1>
          <p className="text-sm text-foreground/50">Practice a real conversation. Get grammar and vocabulary feedback as you go.</p>
        </header>

        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        <SessionControls
          phase={phase}
          starting={starting}
          canPause={canPause}
          onStart={handleStart}
          onTogglePause={handleTogglePause}
          onEnd={handleEndSession}
        />

        <div className="grid flex-1 grid-cols-1 gap-6 lg:grid-cols-[1.2fr_1fr]">
          <div className="flex flex-col gap-6">
            <WaveformHero
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
              onChange={setSetupValue}
              sessionActive={sessionActive}
            />
          </div>

          <div className="flex flex-col gap-6">
            <ConversationView messages={messages} />
            <div className="h-64 shrink-0">
              <CorrectionsPanel
                key={session?.conversationId ?? "no-session"}
                conversationId={session?.conversationId}
                refreshKey={correctionsRefreshKey}
                onCountChange={setCorrectionsCount}
              />
            </div>
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
