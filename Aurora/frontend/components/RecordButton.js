"use client";

import { useRef, useState } from "react";

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

/**
 * Push-to-talk button. Hold to record (mouse or touch), release to send.
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
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const startedAtRef = useRef(0);

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
      // eslint-disable-next-line react-hooks/purity -- this runs inside an event handler (mousedown/touchstart), never during render
      startedAtRef.current = Date.now();
      setRecording(true);
    } catch (err) {
      console.error("[RecordButton] mic access failed:", err);
      onRecordingComplete?.(null, err);
    } finally {
      setRequesting(false);
    }
  }

  function stopRecording() {
    if (!recording) return;
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  function cleanupStream() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
  }

  return (
    <button
      type="button"
      disabled={disabled || requesting}
      onMouseDown={startRecording}
      onMouseUp={stopRecording}
      onMouseLeave={() => recording && stopRecording()}
      onTouchStart={(e) => {
        e.preventDefault();
        startRecording();
      }}
      onTouchEnd={(e) => {
        e.preventDefault();
        stopRecording();
      }}
      className={`flex h-20 w-20 select-none items-center justify-center rounded-full shadow-lg transition-all duration-150 focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-300 disabled:cursor-not-allowed disabled:opacity-40 ${
        recording
          ? "scale-110 bg-rose-500 shadow-rose-300/50"
          : "bg-indigo-600 hover:bg-indigo-500 shadow-indigo-300/50"
      }`}
      aria-pressed={recording}
      aria-label={recording ? "Recording — release to send" : "Hold to talk"}
    >
      <MicIcon className="h-8 w-8 text-white" />
    </button>
  );
}

function MicIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path
        d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M19 11a7 7 0 0 1-14 0" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 18v3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
