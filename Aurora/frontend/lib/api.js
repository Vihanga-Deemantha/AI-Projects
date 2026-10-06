/**
 * AURA backend API client.
 *
 * Mirrors the request/streaming logic already proven out in local_client.py
 * (the Python terminal client) — same endpoints, same NDJSON protocol.
 */

import { expireSession, getToken } from "@/lib/auth";
import { readEvents, StreamStalledError } from "@/lib/ndjson";
import { audioFileName } from "@/lib/recording";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

// How long to wait on the server before giving up on a turn. The first sign of life is the transcript, which
// arrives once speech-to-text has finished; after that a sentence of the reply should turn up every few seconds.
// The server cuts off a stalled language model itself after 30 s (backend/routers/conversation.py), so both
// limits are deliberately longer than that: its own explanation should win when it has one.
const FIRST_BYTE_TIMEOUT_MS = 90_000;
const IDLE_TIMEOUT_MS = 45_000;

/** Raised on 401 so callers/UI can send the user back to /login. */
export class UnauthorizedError extends Error {
  constructor() {
    super("Your session has expired. Please log in again.");
    this.name = "UnauthorizedError";
  }
}

function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

/**
 * fetch wrapper that attaches the Bearer token and turns a 401 into a cleared
 * session, so an expired token can't leave the UI stuck in a half-logged-in
 * state making failing calls.
 */
export async function authFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: authHeaders(options.headers),
  });
  if (res.status === 401) {
    expireSession();
    throw new UnauthorizedError();
  }
  return res;
}

/**
 * The server's own message for a failed request (FastAPI puts it in `detail`),
 * so a rate limit says "Too many attempts…" and an ended session says so,
 * instead of a bare status code.
 */
export async function errorMessage(res, fallback) {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  } catch {
    /* not JSON */
  }
  if (res.status === 429) return "You're doing that too quickly. Please wait a moment and try again.";
  return `${fallback} (${res.status})`;
}

/** Fetches voice/style/scenario options for the session setup picker. */
export async function getOptions() {
  const res = await fetch(`${API_BASE}/api/config/options`);
  if (!res.ok) throw new Error(`Failed to load options (${res.status})`);
  return res.json();
}

/**
 * Creates a new conversation session. The owner is taken from the JWT — there
 * is deliberately no user_id parameter, since the server ignores client-supplied
 * ids now.
 */
export async function startSession({ scenario, style, voice, focus }) {
  const form = new FormData();
  form.set("scenario", scenario);
  form.set("style", style);
  form.set("voice", voice);
  if (focus) form.set("focus", focus); // e.g. "grammar:past_tense" — steers the chat toward a weakness

  const res = await authFetch(`/api/conversation/start`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await errorMessage(res, "Failed to start session"));
  return res.json();
}

/** Marks a session complete so it gets a duration in history. */
export async function endSession(conversationId) {
  const res = await authFetch(`/api/conversation/${conversationId}/end`, { method: "POST" });
  if (!res.ok) throw new Error(await errorMessage(res, "Failed to end session"));
  return res.json();
}

/**
 * A best-effort "End session" for a learner who walks away without pressing the button (a link click, a
 * closed tab). `keepalive` lets the request outlive the page. It reports nothing and has no 401 handling, on
 * purpose: if it is lost (offline, a browser that drops requests while a tab closes) the session simply stays
 * "unfinished", and can be finished from its page in History. The server ends a long-idle session where the
 * learner stopped talking, so a late call never inflates the session's length.
 */
export function endSessionOnLeave(conversationId) {
  const token = getToken();
  if (!token) return;
  fetch(`${API_BASE}/api/conversation/${conversationId}/end`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    keepalive: true,
  }).catch(() => {});
}

/** Past sessions for the logged-in user, newest first. */
export async function getSessions({ limit = 20, offset = 0 } = {}) {
  const res = await authFetch(`/api/history/sessions?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(await errorMessage(res, "Failed to load history"));
  return res.json();
}

/** One past session: full transcript with corrections attached per turn. */
export async function getSession(conversationId) {
  const res = await authFetch(`/api/history/sessions/${conversationId}`);
  if (res.status === 404) throw new Error("Session not found");
  if (!res.ok) throw new Error(await errorMessage(res, "Failed to load session"));
  return res.json();
}

/**
 * Sends a recorded audio blob to the streaming endpoint and invokes callbacks
 * as NDJSON lines arrive. Browser equivalent of local_client.py's
 * `send_audio_streaming()` — same message types, same handling.
 *
 * Message types from the server:
 *   { type: "transcript", text, message_id }
 *   { type: "metrics", message_id, fluency, clarity }
 *   { type: "audio_chunk", index, text, data (b64 wav), tts_ms }
 *   { type: "warning", message }   — non-fatal (e.g. one sentence couldn't be spoken)
 *   { type: "done", full_reply, timings }
 *   { type: "error", message }
 *
 * @param {string} conversationId
 * @param {Blob} audioBlob
 * @param {{
 *   onTranscript?: (text: string, messageId: string) => void,
 *   onMetrics?: (metrics: {message_id:string, fluency:object|null, clarity:object|null}) => void,
 *   onAudioChunk?: (chunk: {index:number, text:string, data:string, tts_ms:number}) => void,
 *   onWarning?: (message: string) => void,
 *   onDone?: (payload: {full_reply:string, timings:object}) => void,
 *   onError?: (message: string) => void,
 * }} handlers
 * @param {{ signal?: AbortSignal, firstByteMs?: number, idleMs?: number }} [options]
 *   `signal` lets the caller give up (the learner left the page): the request is cancelled, so the server stops
 *   working on a reply nobody is waiting for, and the returned promise rejects with an AbortError (no handler is
 *   called). A reply that stalls, or whose connection drops before "done", is reported through `onError` and
 *   rejects, rather than leaving the learner waiting in silence.
 */
export async function streamMessage(conversationId, audioBlob, handlers = {}, { signal, firstByteMs = FIRST_BYTE_TIMEOUT_MS, idleMs = IDLE_TIMEOUT_MS } = {}) {
  const form = new FormData();
  form.set("conversation_id", conversationId);
  // Named after what the browser really recorded (Safari: MP4, not WebM): the server keeps the ending.
  form.set("audio_file", audioBlob, audioFileName(audioBlob));

  // One controller for everything below. The caller leaving and our own timeouts both abort it, which also
  // closes the connection.
  const controller = new AbortController();
  const forwardAbort = () => controller.abort(signal.reason);
  if (signal?.aborted) controller.abort(signal.reason);
  else signal?.addEventListener("abort", forwardAbort, { once: true });
  const firstByteTimer = setTimeout(() => controller.abort(new StreamStalledError()), firstByteMs);

  let finished = false; // a "done" or "error" message arrived, so the reply is complete one way or another
  try {
    const res = await authFetch(`/api/conversation/message-stream`, {
      method: "POST",
      body: form,
      signal: controller.signal,
    });
    clearTimeout(firstByteTimer);

    if (!res.ok || !res.body) {
      const message = await errorMessage(res, "Couldn't send that recording");
      handlers.onError?.(message);
      throw new Error(message);
    }

    await readEvents(res.body, {
      signal: controller.signal,
      idleMs,
      onMessage: (msg) => {
        if (msg.type === "done" || msg.type === "error") finished = true;
        dispatch(msg, handlers);
      },
    });

    if (!finished) {
      // The stream closed without a "done": the connection dropped part-way through the reply.
      const message = "The connection dropped before the reply finished. Please try again.";
      handlers.onError?.(message);
      throw new Error(message);
    }
  } catch (err) {
    // Some browsers reject an aborted fetch with a plain AbortError rather than the reason it was aborted with.
    const stalled = err instanceof StreamStalledError || (!signal?.aborted && controller.signal.reason instanceof StreamStalledError);
    if (stalled) {
      const message = new StreamStalledError().message;
      handlers.onError?.(message);
      throw new StreamStalledError(message);
    }
    throw err;
  } finally {
    clearTimeout(firstByteTimer);
    signal?.removeEventListener("abort", forwardAbort);
    controller.abort(); // closes the connection if it is somehow still open; harmless once it has finished
  }
}

function dispatch(msg, handlers) {
  switch (msg.type) {
    case "transcript":
      handlers.onTranscript?.(msg.text, msg.message_id);
      break;
    case "metrics":
      handlers.onMetrics?.(msg);
      break;
    case "audio_chunk":
      handlers.onAudioChunk?.(msg);
      break;
    case "warning":
      handlers.onWarning?.(msg.message);
      break;
    case "done":
      handlers.onDone?.(msg);
      break;
    case "error":
      handlers.onError?.(msg.message);
      break;
    default:
      break;
  }
}

/**
 * Recent grammar/vocab corrections for a conversation, plus `pending` — how
 * many of the user's turns are still being analysed. The panel keeps polling
 * while pending > 0 and stops the moment it reaches 0.
 */
export async function getRecentCorrections(conversationId, limit = 5) {
  const res = await authFetch(
    `/api/analysis/conversation/${conversationId}/recent?limit=${limit}`
  );
  if (!res.ok) throw new Error(await errorMessage(res, "Failed to fetch corrections"));
  return res.json();
}

/**
 * The report for a finished session. Resolves to:
 *   { status: "ready", report }   — the finished report
 *   { status: "pending" }         — still being written (the last turn is being analysed); ask again
 *   { status: "none", message }   — nothing was said, so there is nothing to report on
 *   { status: "running" }         — the session hasn't ended yet
 */
export async function getSessionReport(conversationId) {
  const res = await authFetch(`/api/history/sessions/${conversationId}/report`);
  if (res.status === 202) return { status: "pending" };
  if (res.status === 409) return { status: "running" };
  if (res.status === 404) {
    const data = await res.json().catch(() => ({}));
    if (data.detail && /no turns/i.test(data.detail)) return { status: "none", message: data.detail };
    throw new Error("Session not found");
  }
  if (!res.ok) throw new Error(await errorMessage(res, "Failed to load the report"));
  return res.json();
}

/** Progress over time (weekly trends, streak, totals, milestones). Days and weeks are the learner's own. */
export async function getProgress({ weeks = 12 } = {}) {
  const tzOffset = -new Date().getTimezoneOffset(); // minutes ahead of UTC (e.g. +330 in India)
  const res = await authFetch(`/api/progress/summary?weeks=${weeks}&tz_offset=${tzOffset}`);
  if (!res.ok) throw new Error(await errorMessage(res, "Failed to load your progress"));
  return res.json();
}

/** What to practise today: the learner's top live weakness (or a starter if they have no history yet). */
export async function getPracticeToday() {
  const res = await authFetch("/api/practice/today");
  if (!res.ok) throw new Error(await errorMessage(res, "Failed to load today's practice"));
  return res.json();
}

/**
 * How demanding the next session will be, and why:
 * { mode: "auto" | "manual", tier, label, example, auto_tier, auto_label, trend: "up" | "down" | "same", reason, recent_scores }
 */
export async function getDifficulty() {
  const res = await authFetch("/api/practice/difficulty");
  if (!res.ok) throw new Error(await errorMessage(res, "Failed to load your difficulty level"));
  return res.json();
}

/** The learner's weakness profile: what they keep getting wrong, and whether it is improving. */
export async function getWeaknesses() {
  const res = await authFetch("/api/practice/weaknesses");
  if (!res.ok) throw new Error(await errorMessage(res, "Failed to load your focus areas"));
  return res.json();
}
