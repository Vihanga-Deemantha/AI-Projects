"use client";

import { useEffect, useRef, useState } from "react";

const CANDIDATE_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
];

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return "";
  for (const type of CANDIDATE_MIME_TYPES) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return ""; // let the browser pick its default
}

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

/**
 * Push-to-talk bar. Hold to record (mouse, touch or pen), release to send.
 * Records via MediaRecorder — produces webm/opus (or ogg/opus on Firefox),
 * not WAV like local_client.py's sounddevice-based recorder. faster-whisper
 * decodes both via its `av` (PyAV/ffmpeg) dependency, but very short holds
 * can produce a container PyAV can't demux — see MIN_RECORDING_MS below.
 *
 * Reports the live mic AnalyserNode up to the parent while recording, so the
 * waveform hero can visualize actual mic input instead of a canned animation.
 */
export default function RecordButton({ disabled, onRecordingComplete, onAnalyser }) {
  const [recording, setRecording] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const startedAtRef = useRef(0);
  const maxTimerRef = useRef(null);
  // Whether the pointer is still down. Opening the mic takes a moment (and can
  // wait on a permission prompt); if the user lets go in the meantime there is
  // nothing to stop yet, so the release has to be remembered and applied the
  // instant recording begins.
  const pointerHeldRef = useRef(false);

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
    setRequesting(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Wire the live mic stream into an analyser for waveform visualization.
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      audioCtxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      onAnalyser?.(analyser);

      const mimeType = pickMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        chunksRef.current = [];
        cleanupStream();
        onAnalyser?.(null);

        const durationMs = Date.now() - startedAtRef.current;
        if (durationMs < MIN_RECORDING_MS) {
          onRecordingComplete?.(null, { name: "TooShortError" });
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
      if (!pointerHeldRef.current) stopRecording();
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

  function release() {
    pointerHeldRef.current = false;
    stopRecording();
  }

  const seconds = Math.floor(elapsedMs / 1000);
  const clock = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  const nearLimit = recording && elapsedMs > MAX_RECORDING_MS - 10_000;
  const label = recording
    ? `Release to send · ${clock}${nearLimit ? ` (max ${MAX_RECORDING_MS / 1000}s)` : ""}`
    : requesting
      ? "Starting mic…"
      : "Hold to speak";

  return (
    <button
      type="button"
      disabled={disabled || requesting}
      // Pointer Events (not separate mouse/touch handlers) so mouse, touch,
      // and pen all go through one path with no synthetic-mouse-after-touch
      // double-fire, and setPointerCapture keeps the up/cancel event routed
      // here even if a finger drifts off the button mid-hold. touch-none
      // (below) stops the browser from treating the hold as a page-scroll
      // gesture, which is what onTouchStart's now-ineffective preventDefault
      // was trying (and failing, since React's touch listeners are passive)
      // to do.
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture?.(e.pointerId);
        pointerHeldRef.current = true;
        startRecording();
      }}
      onPointerUp={release}
      onPointerCancel={release}
      className={`flex h-14 w-full touch-none items-center justify-center gap-3 text-[11px] font-bold tracking-[0.2em] uppercase transition select-none focus:outline-none focus-visible:ring-4 focus-visible:ring-brand/40 disabled:cursor-not-allowed disabled:opacity-50 ${
        recording ? "cursor-pointer bg-brand text-on-brand" : "cursor-pointer bg-foreground text-background hover:bg-brand hover:text-on-brand"
      }`}
      aria-pressed={recording}
      aria-label={recording ? "Recording — release to send" : "Hold to talk"}
    >
      <MicIcon className="h-4 w-4" />
      {label}
    </button>
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
