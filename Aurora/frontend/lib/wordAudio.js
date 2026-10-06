/**
 * "Hear this word": plays one word, spoken by a companion's voice, optionally
 * slowly (POST /api/speech/word). Only one word plays at a time — starting
 * another cuts the previous one off, so rapid clicking can't pile up audio.
 */
import { authFetch, errorMessage } from "@/lib/api";

let current = null; // { audio, url }

function stopCurrent() {
  if (!current) return;
  current.audio.pause();
  URL.revokeObjectURL(current.url);
  current = null;
}

/**
 * Fetches and plays the word. Resolves when playback ENDS; rejects with a readable message on failure.
 * `style` is the session's speaking style, so the word is said in the accent the session was spoken in.
 */
export async function playWord({ word, voice, style, slow = false }) {
  stopCurrent();

  // authFetch also signs the learner out cleanly if their session has expired.
  const res = await authFetch("/api/speech/word", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ word, voice: voice || undefined, style: style || undefined, slow }),
  });
  if (!res.ok) throw new Error(await errorMessage(res, "Couldn't play that word"));

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  current = { audio, url };

  return new Promise((resolve, reject) => {
    audio.onended = () => {
      if (current?.audio === audio) stopCurrent();
      resolve();
    };
    audio.onerror = () => {
      if (current?.audio === audio) stopCurrent();
      reject(new Error("Couldn't play that audio."));
    };
    audio.play().catch((err) => {
      if (current?.audio === audio) stopCurrent();
      reject(err);
    });
  });
}
