/**
 * Recording the microphone: which format to ask the browser for, what to call the upload, whether this
 * browser can record at all, and what to tell the learner when it can't. Pure functions, so the browser
 * differences (Chrome records WebM, Firefox Ogg, Safari MP4) are unit-tested (lib/recording.test.js).
 */

// In order of preference. Chrome and Edge record WebM, Firefox Ogg and Safari MP4 (AAC); the server accepts all of them.
export const RECORDING_MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];

/** The first format the browser can record (`isSupported` is MediaRecorder.isTypeSupported), or "" to let it choose. */
export function pickRecordingMimeType(isSupported) {
  return RECORDING_MIME_CANDIDATES.find((type) => isSupported(type)) ?? "";
}

/**
 * The upload's file name, from what was actually recorded. The server keeps the ending when it saves the
 * file (backend/routers/conversation.py), so a Safari recording must not be called ".webm".
 */
export function audioFileName(blob) {
  const type = (blob?.type || "").toLowerCase();
  if (/mp4|m4a|aac/.test(type)) return "audio.m4a";
  if (type.includes("ogg")) return "audio.ogg";
  if (type.includes("wav")) return "audio.wav";
  return "audio.webm";
}

/**
 * Why recording cannot even start here, as an error name `micErrorMessage` understands, or null when it can.
 * Browsers only offer the microphone on secure pages (https, or localhost), and `navigator.mediaDevices` is
 * simply missing elsewhere, which would otherwise surface as a baffling "could not access the microphone".
 */
export function recordingSupportProblem(env = globalThis) {
  if (typeof env.MediaRecorder === "undefined") return "UnsupportedError";
  if (!env.navigator?.mediaDevices?.getUserMedia) {
    return env.isSecureContext === false ? "InsecureContextError" : "UnsupportedError";
  }
  return null;
}

/** What to tell the learner for a microphone failure. `mode` ("hold" or "tap") words the too-short advice. */
export function micErrorMessage(err, mode = "hold") {
  switch (err?.name) {
    case "NotAllowedError":
      return "Microphone permission was denied or dismissed. Click the mic/lock icon in your browser's address bar, allow microphone access, then try again.";
    case "NotFoundError":
      return "No microphone was found. Check that one is connected and try again.";
    case "NotReadableError":
      return "Your microphone is already in use by another app. Close it and try again.";
    case "TooShortError":
      return mode === "tap"
        ? "That was too short to send — tap to start, speak, then tap again to send."
        : "That was too short to send — hold the mic button down while you speak, then release.";
    case "InsecureContextError":
      return "The microphone only works on a secure page. Open AURA over https (or on localhost) and try again.";
    case "UnsupportedError":
      return "This browser can't record audio. Try a recent version of Chrome, Edge, Firefox or Safari.";
    default:
      return "Could not access the microphone. Check your browser's permission settings and try again.";
  }
}
