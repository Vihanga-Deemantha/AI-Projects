"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import SessionSetup from "@/components/SessionSetup";
import SessionControls from "@/components/SessionControls";
import StatsRow from "@/components/StatsRow";
import WaveformHero from "@/components/WaveformHero";
import ConversationView from "@/components/ConversationView";
import CorrectionsPanel from "@/components/CorrectionsPanel";
import LatencyBadge from "@/components/LatencyBadge";
import TodaysPractice from "@/components/TodaysPractice";
import { endSession, endSessionOnLeave, getDifficulty, getOptions, getPracticeToday, startSession, streamMessage } from "@/lib/api";
import { getStoredUser, onUserUpdated, updateProfile } from "@/lib/auth";
import { getCompanion } from "@/lib/characters";
import { speaks } from "@/lib/accents";
import { createAudioQueue } from "@/lib/audioQueue";
import { formatClock } from "@/lib/format";
import { micErrorMessage } from "@/lib/recording";

let nextMessageId = 1;

export default function PracticePage() {
  return (
    // Practice reads ?focus=... (set by the "Practise this" links on the progress page).
    <Suspense fallback={null}>
      <Practice />
    </Suspense>
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
  // Non-fatal heads-up from the server (e.g. one sentence couldn't be spoken).
  const [notice, setNotice] = useState(null);
  const [playbackAnalyser, setPlaybackAnalyser] = useState(null);
  const [user, setUser] = useState(null);
  // Today's practice (Phase 9): the learner's top live weakness, and the focus chosen for the next session.
  const [today, setToday] = useState(null);
  const [focus, setFocus] = useState(null);
  // Difficulty (Phase 10): the level the NEXT session will run at, and the level of the one that is running.
  const [level, setLevel] = useState(null);
  const [sessionLevel, setSessionLevel] = useState(null);
  const searchParams = useSearchParams();
  const refreshTodayTimerRef = useRef(null);

  // Said aloud to screen-reader users (and shown to no one else): what the recogniser heard them say.
  const [announcement, setAnnouncement] = useState("");

  const audioQueueRef = useRef(null);
  const saveQueueRef = useRef(Promise.resolve()); // profile saves from the setup panel, one at a time
  const currentAuraMessageIdRef = useRef(null);
  const liveSessionRef = useRef(null); // the id of the session that is open right now, if any
  // May the coach's voice play? True while a session is open. Once it has ended, or the learner has left the page,
  // a reply that is still arriving must not start new audio (its text still lands, so the transcript is complete).
  const voiceOnRef = useRef(false);
  const endedWhileHiddenRef = useRef(false); // the session was ended because the page was put away (see the pagehide listener)
  const handleEndSessionRef = useRef(null);

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
        const voice = valid(opts.voices, saved?.preferred_voice, opts.defaults.voice);
        // A style brings an accent, and not every companion has a voice for every accent: if the saved pair
        // doesn't work, start from Standard English rather than from a pair the server would refuse.
        const savedStyle = valid(opts.styles, saved?.preferred_style, opts.defaults.style);
        const style = speaks(opts, voice, savedStyle) ? savedStyle : opts.defaults.style;
        setSetupValue({ voice, style, scenario: opts.defaults.scenario });
        // Arriving from a "Practise this" link: preselect that focus and the scenario where it comes up naturally.
        const wanted = searchParams.get("focus");
        const area = wanted && opts.focus_areas?.find((f) => f.id === wanted);
        if (area) {
          setFocus(area.id);
          setSetupValue((prev) => ({ ...prev, scenario: opts.scenarios.some((x) => x.id === area.scenario) ? area.scenario : prev.scenario }));
        }
      })
      .catch(() => setError("Could not reach the AURA backend. Is it running on port 8000?"));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount; the focus param is only read at arrival
  }, []);

  // Today's practice and the difficulty level, plus a refresh timer cleaned up on unmount.
  useEffect(() => {
    refreshGuidance();
    return () => clearTimeout(refreshTodayTimerRef.current);
  }, []);

  // Guidance is a nicety; it must never block practising, so a failure is just ignored.
  function refreshGuidance() {
    getPracticeToday().then((r) => setToday(r.exercise)).catch(() => {});
    getDifficulty().then(setLevel).catch(() => {});
  }

  // Session timer. Stops (without resetting) the moment the session ends, so
  // the recap shows the elapsed time the conversation actually ran for.
  useEffect(() => {
    if (!session || sessionEnded) return;
    const start = Date.now();
    const id = setInterval(() => setSessionSeconds((Date.now() - start) / 1000), 1000);
    return () => clearInterval(id);
  }, [session, sessionEnded]);

  // Which session is open right now, in a ref the cleanup below can read without re-subscribing on every change.
  useEffect(() => {
    liveSessionRef.current = session && !sessionEnded ? session.conversationId : null;
  }, [session, sessionEnded]);

  // The listeners below live as long as the page and must call the CURRENT version of handleEndSession.
  useEffect(() => {
    handleEndSessionRef.current = handleEndSession;
  });

  // Leaving this page (a link inside the app, a closed tab, another site) without pressing "End session": stop the
  // coach mid-sentence and end the session, so it gets its report instead of staying "unfinished" for good. A
  // reply that is still arriving is deliberately NOT cancelled: the server saves the coach's reply only when it has
  // finished, and cutting it off would leave the last turn in History with no answer.
  useEffect(() => {
    const endOpenSession = () => {
      const id = liveSessionRef.current;
      if (!id) return false;
      liveSessionRef.current = null;
      endSessionOnLeave(id);
      return true;
    };
    // The page is being put away: closed, sent to another site, or kept in the browser's back/forward cache.
    const onPageHide = () => {
      if (endOpenSession()) endedWhileHiddenRef.current = true;
    };
    // The Back button can bring a cached page back exactly as it was left, with its session looking live. That session
    // is over, so show it as the ended one it is, rather than as one whose next turn the server would refuse.
    const onPageShow = (e) => {
      if (e.persisted && endedWhileHiddenRef.current) {
        endedWhileHiddenRef.current = false;
        handleEndSessionRef.current?.();
      }
    };
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("pageshow", onPageShow);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("pageshow", onPageShow);
      endOpenSession();
      voiceOnRef.current = false;
      audioQueueRef.current?.close();
      audioQueueRef.current = null;
    };
  }, []);

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
  // failed save shouldn't block starting a session. Saves go one at a time and
  // each carries the whole pair, because the server only accepts a style the
  // companion can speak: a style picked right after a companion must not be
  // checked against the companion that was saved before it.
  function handleSetupChange(next) {
    const changed = next.voice !== setupValue.voice || next.style !== setupValue.style;
    setSetupValue(next);
    if (changed) {
      saveQueueRef.current = saveQueueRef.current.then(() =>
        updateProfile({ preferredVoice: next.voice, preferredStyle: next.style }).catch(() => {}),
      );
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

    const data = await startSession({ ...setupValue, focus });
    const newSession = { conversationId: data.conversation_id, style: data.style };
    setSession(newSession);
    setSessionLevel(data.difficulty ?? null);
    setSessionEnded(false);
    setMessages([]);
    setTurns(0);
    setSessionSeconds(0);
    setTimings(null);
    setCorrectionsCount(0);
    setCorrectionsRefreshKey(0);
    setError(null);
    setNotice(null);
    voiceOnRef.current = true;
    getAudioQueue();
    return newSession;
  }

  /**
   * The mic was pressed (a click, a touch or a key): wake the audio system now, inside the gesture. Browsers such
   * as Safari only let sound start from a user gesture, and the first reply arrives long after the press.
   */
  function handleMicPress() {
    getAudioQueue().unlock();
  }

  async function handleStart() {
    setStarting(true);
    setError(null);
    handleMicPress(); // the Start button is a gesture too, and it creates the audio queue after a network wait otherwise
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
    voiceOnRef.current = false; // a reply still arriving may add its text, but must not start new audio
    audioQueueRef.current?.close();
    audioQueueRef.current = null;
    setPlaybackAnalyser(null);
    setPaused(false);
    setSessionEnded(true);
    // The last turn's grammar/vocab analysis may still be running. Ask the
    // corrections panel to look again: it keeps polling for as long as the
    // server says analysis is pending, so a slow one still makes it into the
    // recap instead of the count freezing one short.
    if (session) {
      setCorrectionsRefreshKey((k) => k + 1);
    }
    // The focus was for THIS session; and the session's mistakes and score change what is worth
    // practising next and how hard it should be, so look again once its report has been written
    // (usually seconds, but it waits for the last answer's analysis, so look once more later too).
    setFocus(null);
    clearTimeout(refreshTodayTimerRef.current);
    refreshTodayTimerRef.current = setTimeout(() => {
      refreshGuidance();
      refreshTodayTimerRef.current = setTimeout(refreshGuidance, 14000);
    }, 6000);
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

  /** A reply that never finished (a dropped connection, an error) must not stay behind as a faded "…" bubble. */
  function settlePending() {
    setMessages((prev) => prev.map((m) => (m.pending ? { ...m, pending: false } : m)));
    currentAuraMessageIdRef.current = null;
  }

  async function handleRecordingComplete(blob, recordingError) {
    if (recordingError) {
      setError(micErrorMessage(recordingError, recordingError.mode));
      return;
    }
    if (!blob) return;

    setError(null);
    setNotice(null);
    setIsProcessing(true);
    currentAuraMessageIdRef.current = null;

    try {
      // Holding the mic is enough to start a session — no separate button required.
      const activeSession = await ensureSession();

      await streamMessage(activeSession.conversationId, blob, {
        onTranscript: (text, messageId) => {
          setAnnouncement(`You said: ${text}`);
          setMessages((prev) => [
            ...prev,
            { id: nextMessageId++, messageId, role: "user", text, timestamp: nowLabel() },
          ]);
        },
        // How they spoke (rate, pauses, fillers) arrives right after the transcript.
        onMetrics: ({ message_id, fluency, clarity }) => {
          if (!fluency && !clarity) return;
          setMessages((prev) => prev.map((m) => (m.messageId === message_id ? { ...m, fluency, clarity } : m)));
        },
        onAudioChunk: (chunk) => {
          if (voiceOnRef.current) getAudioQueue().enqueue(chunk.data, chunk.text);
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
        onWarning: (message) => setNotice(message),
        onError: (message) => {
          setError(message);
          settlePending();
          setIsProcessing(false);
        },
      });
    } catch (err) {
      setError(err.message);
      settlePending();
    } finally {
      setIsProcessing(false);
    }
  }

  const sessionActive = Boolean(session) && !sessionEnded;

  // Single source of truth for the session status badge + controls, shared
  // between SessionControls and WaveformHero so they never disagree.
  // Holding the mic is "listening" even before the first turn has created a
  // session (the session is opened when the recording is sent).
  let phase = "idle";
  if (micAnalyser) {
    phase = "recording";
  } else if (sessionActive) {
    if (isProcessing) phase = "thinking";
    else if (paused) phase = "paused";
    else if (isPlaying) phase = "speaking";
    else phase = "active";
  } else if (session && sessionEnded) {
    phase = "ended";
  }
  const canPause = phase === "speaking" || phase === "paused";

  // Session averages across the turns that have metrics so far.
  const average = (scores) => (scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null);
  const avgFluency = average(messages.filter((m) => m.fluency).map((m) => m.fluency.score));
  const avgClarity = average(messages.filter((m) => m.clarity).map((m) => m.clarity.score));

  const focusLabel = options?.focus_areas?.find((f) => f.id === focus)?.label ?? today?.label;

  function acceptTodaysPractice(exercise) {
    setFocus(exercise.focus);
    if (options?.scenarios.some((x) => x.id === exercise.suggested_scenario)) {
      setSetupValue((prev) => ({ ...prev, scenario: exercise.suggested_scenario }));
    }
  }

  const companion = getCompanion(setupValue.voice);
  const scenarioLabel = options?.scenarios.find((x) => x.id === setupValue.scenario)?.label;
  const awaitingReply = isProcessing && !messages.some((m) => m.pending);

  return (
    <main className="min-w-0 flex-1 px-5 py-6 sm:px-8 sm:py-8 lg:px-10 lg:pt-9 lg:pb-14">
      {/* For screen readers only: what the recogniser heard. The coach's reply is not repeated here: it is spoken aloud. */}
      <div role="status" className="sr-only">
        {announcement}
      </div>

      <header className="flex flex-wrap items-end justify-between gap-4.5">
        <div>
          <div className="text-[10px] font-bold tracking-[0.22em] text-soft uppercase">Session</div>
          <h1 className="mt-2.5 font-display text-[clamp(30px,3.6vw,46px)] leading-none font-bold">Practise English</h1>
        </div>
        <SessionControls
          phase={phase}
          hasSession={sessionActive}
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
      {notice && !error && (
        <div role="status" className="mt-5 border border-panel-border bg-field px-4 py-3 text-sm text-soft">
          {notice}
        </div>
      )}

      {phase === "ended" && (
        <div role="status" className="mt-5 border border-brand bg-brand-soft px-4.5 py-3.5 text-sm">
          <strong className="font-bold">Session complete.</strong>{" "}
          {turns} {turns === 1 ? "turn" : "turns"} · {formatClock(sessionSeconds)} ·{" "}
          {correctionsCount} {correctionsCount === 1 ? "correction" : "corrections"} — saved to your history.
          Ready when you are — hold the mic or use &ldquo;Start new session&rdquo; above.
          {turns > 0 && session && (
            <div className="mt-3">
              <Link
                href={`/history/${session.conversationId}/report`}
                className="inline-flex h-10 items-center bg-foreground px-4.5 text-[10px] font-bold tracking-[0.16em] text-background uppercase transition hover:bg-brand hover:text-on-brand"
              >
                See your report &rarr;
              </Link>
            </div>
          )}
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
            onPress={handleMicPress}
            onRecordingComplete={handleRecordingComplete}
          />

          {timings && (
            <div className="flex justify-center">
              <LatencyBadge timings={timings} />
            </div>
          )}

          <StatsRow
            turns={turns}
            sessionSeconds={sessionSeconds}
            correctionsCount={correctionsCount}
            fluencyScore={avgFluency}
            clarityScore={avgClarity}
          />

          <TodaysPractice
            exercise={today}
            focus={focus}
            label={focusLabel}
            sessionActive={sessionActive}
            onAccept={acceptTodaysPractice}
            onClear={() => setFocus(null)}
          />

          <SessionSetup
            options={options}
            value={setupValue}
            onChange={handleSetupChange}
            sessionActive={sessionActive}
            difficulty={sessionActive ? sessionLevel : level}
          />
        </div>

        <div className="flex min-w-0 flex-col gap-5.5">
          <ConversationView
            messages={messages}
            companionId={companion.id}
            style={session?.style ?? setupValue.style}
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
  );
}

function nowLabel() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
