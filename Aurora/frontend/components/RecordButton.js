"use client";

import { useEffect, useRef, useState } from "react";
import { formatClock } from "@/lib/format";
import { pickRecordingMimeType, recordingSupportProblem } from "@/lib/recording";

// Recordings shorter than this are rejected client-side rather than sent to
// the backend. Very short holds (an accidental tap, or releasing before the
// encoder has written a real frame) can produce a webm container that's
// technically non-empty but has no decodable audio in it — ffmpeg/PyAV then
// fails with a raw "End of file" demux error. Catching it here gives an
// instant, friendly message instead of a round trip that fails anyway.
const MIN_RECORDING_MS = 400;

// A single spoken turn is capped at a minute: the server rejects bigger uploads
// anyway, and a held button that never got its pointer-up must not record forever.
const MAX_RECORDING_MS = 60_000;

// The learner's choice between holding the button and tapping it, remembered in this browser only.
const MODE_KEY = "aura_mic_mode";

const isActivationKey = (e) => e.key === " " || e.key === "Enter";

/**
 * The talk button. Two ways to use it, both reachable without a mouse:
 *  - "hold" (the default): hold to record, release to send. A mouse, a finger or a pen works, and so does holding
 *    Space or Enter while the button is focused.
 *  - "tap": tap to start, tap again to send. For anyone who cannot comfortably hold a button down for a whole
 *    sentence (a keyboard user, a trackpad, a long answer on a phone).
 * Records via MediaRecorder: WebM/Opus in Chrome and Edge, Ogg/Opus in Firefox, MP4 in Safari. The server
 * decodes all of them (faster-whisper through its `av` dependency).
 *
 * Reports the live mic AnalyserNode up to the parent while recording, so the waveform hero can visualize the
 * actual mic input instead of a canned animation, and calls `onPress` synchronously at the start of every press
 * so the parent can unlock audio playback inside the user gesture (Safari refuses to play sound otherwise).
 */
export default function RecordButton({ disabled, onRecordingComplete, onAnalyser, onPress }) {
  const [recording, setRecording] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [mode, setMode] = useState("hold");
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const startedAtRef = useRef(0);
  const maxTimerRef = useRef(null);
  // Whether the press that began this recording is still down (a pointer, a key, or in tap mode until the second
  // tap). Opening the mic takes a moment (and can wait on a permission prompt); if the learner lets go in the
  // meantime there is nothing to stop yet, so the release has to be remembered and applied the instant recording begins.
  const pressHeldRef = useRef(false);
  const keyHeldRef = useRef(false);

  // The saved choice of mode, read after mount because localStorage is not available while rendering on the server.
  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is client-only; reading it during render would mismatch SSR output
      if (localStorage.getItem(MODE_KEY) === "tap") setMode("tap");
    } catch {
      /* storage unavailable: stay on hold-to-talk */
    }
  }, []);

  // Live "0:07" readout while recording.
  useEffect(() => {
    if (!recording) return;
    const id = setInterval(() => setElapsedMs(Date.now() - startedAtRef.current), 250);
    return () => clearInterval(id);
  }, [recording]);

  // Never leave the microphone open if the button unmounts mid-recording.
  useEffect(
    () => () => {
      clearTimeout(maxTimerRef.current);
      const recorder = mediaRecorderRef.current;
      if (recorder && recorder.state === "recording") {
        recorder.onstop = null;
        recorder.stop();
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      audioCtxRef.current?.close().catch(() => {});
    },
    []
  );

  async function startRecording() {
    if (disabled || recording || requesting) return;

    const problem = recordingSupportProblem();
    if (problem) {
      onRecordingComplete?.(null, { name: problem });
      return;
    }

    setRequesting(true);
    // Made now, inside the press, rather than after the permission prompt: Safari only lets an audio context
    // run if a user gesture created it.
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const audioCtx = new AudioCtx();
    audioCtxRef.current = audioCtx;
    audioCtx.resume?.().catch(() => {});

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Wire the live mic stream into an analyser for waveform visualization.
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      onAnalyser?.(analyser);

      const mimeType = pickRecordingMimeType((type) => MediaRecorder.isTypeSupported(type));
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const type = recorder.mimeType || chunksRef.current[0]?.type || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        chunksRef.current = [];
        cleanupStream();
        onAnalyser?.(null);

        const durationMs = Date.now() - startedAtRef.current;
        if (durationMs < MIN_RECORDING_MS) {
          onRecordingComplete?.(null, { name: "TooShortError", mode });
          return;
        }
        if (blob.size > 0) onRecordingComplete?.(blob);
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      startedAtRef.current = Date.now();
      setElapsedMs(0);
      setRecording(true);
      maxTimerRef.current = setTimeout(stopRecording, MAX_RECORDING_MS);

      // Released while the mic was still opening: stop straight away (the
      // too-short check then reports it, rather than recording unattended).
      if (!pressHeldRef.current) stopRecording();
    } catch (err) {
      console.error("[RecordButton] mic access failed:", err);
      cleanupStream();
      onAnalyser?.(null);
      onRecordingComplete?.(null, err);
    } finally {
      setRequesting(false);
    }
  }

  function stopRecording() {
    clearTimeout(maxTimerRef.current);
    // Read the recorder itself rather than React state: this is also called from
    // a timer and from inside startRecording, where `recording` would be stale.
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state !== "recording") return;
    recorder.stop();
    setRecording(false);
  }

  function cleanupStream() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
  }

  /** The start of a press: tell the parent (synchronously, inside the gesture), then open the mic. */
  function begin() {
    pressHeldRef.current = true;
    onPress?.();
    startRecording();
  }

  function release() {
    pressHeldRef.current = false;
    stopRecording();
  }

  function switchMode() {
    const next = mode === "hold" ? "tap" : "hold";
    setMode(next);
    try {
      localStorage.setItem(MODE_KEY, next);
    } catch {
      /* storage unavailable: the choice just won't survive a reload */
    }
  }

  const tap = mode === "tap";
  const clock = formatClock(elapsedMs / 1000);
  const nearLimit = recording && elapsedMs > MAX_RECORDING_MS - 10_000;
  const label = recording
    ? `${tap ? "Tap to send" : "Release to send"} · ${clock}${nearLimit ? ` (max ${MAX_RECORDING_MS / 1000}s)` : ""}`
    : requesting
      ? "Starting mic…"
      : tap
        ? "Tap to speak"
        : "Hold to speak";

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        disabled={disabled}
        // A `disabled` button stops receiving the release of the press that is still down, so while the mic is
        // opening the button is only marked aria-disabled: the release must still get through.
        aria-disabled={requesting || undefined}
        aria-describedby="mic-hint"
        // Pointer Events (not separate mouse/touch handlers) so mouse, touch,
        // and pen all go through one path with no synthetic-mouse-after-touch
        // double-fire, and setPointerCapture keeps the up/cancel event routed
        // here even if a finger drifts off the button mid-hold. touch-none
        // (below) stops the browser from treating the hold as a page-scroll
        // gesture, which is what onTouchStart's now-ineffective preventDefault
        // was trying (and failing, since React's touch listeners are passive)
        // to do.
        onPointerDown={(e) => {
          if (tap) return;
          e.currentTarget.setPointerCapture?.(e.pointerId);
          begin();
        }}
        onPointerUp={() => !tap && release()}
        onPointerCancel={() => !tap && release()}
        // The keyboard version of holding: Space or Enter down starts, up sends. preventDefault stops the
        // browser turning the same key press into a click as well. Losing focus counts as letting go.
        onKeyDown={(e) => {
          if (tap || e.repeat || !isActivationKey(e)) return;
          e.preventDefault();
          keyHeldRef.current = true;
          begin();
        }}
        onKeyUp={(e) => {
          if (tap || !isActivationKey(e) || !keyHeldRef.current) return;
          e.preventDefault();
          keyHeldRef.current = false;
          release();
        }}
        onBlur={() => {
          if (keyHeldRef.current) {
            keyHeldRef.current = false;
            release();
          }
        }}
        // Tap mode: a click (a tap, or Enter/Space, which browsers turn into a click) starts, and the next one sends.
        onClick={() => {
          if (!tap) return;
          if (recording || requesting) release();
          else begin();
        }}
        className={`flex h-14 w-full touch-none items-center justify-center gap-3 text-[11px] font-bold tracking-[0.2em] uppercase transition select-none focus:outline-none focus-visible:ring-4 focus-visible:ring-brand/40 disabled:cursor-not-allowed disabled:opacity-50 ${
          requesting ? "opacity-50" : ""
        } ${recording ? "cursor-pointer bg-brand text-on-brand" : "cursor-pointer bg-foreground text-background hover:bg-brand hover:text-on-brand"}`}
        aria-pressed={recording}
        aria-label={recording ? (tap ? "Recording — tap to send" : "Recording — release to send") : tap ? "Tap to talk" : "Hold to talk"}
      >
        <MicIcon className="h-4 w-4" />
        {label}
      </button>

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs leading-normal text-mute">
        <span id="mic-hint">
          {tap ? "Tap to start recording, tap again to send." : "Hold to record, release to send. With a keyboard, hold Space or Enter."}
        </span>
        <button
          type="button"
          onClick={switchMode}
          disabled={recording || requesting}
          className="cursor-pointer underline underline-offset-[3px] transition hover:text-brand disabled:cursor-not-allowed disabled:no-underline disabled:opacity-60"
        >
          {tap ? "Switch to hold-to-talk" : "Switch to tap-to-talk"}
        </button>
      </div>
    </div>
  );
}

function MicIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" {...props}>
      <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M19 11a7 7 0 0 1-14 0" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 18v3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
