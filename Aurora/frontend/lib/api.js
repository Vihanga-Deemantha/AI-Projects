/**
 * AURA backend API client.
 *
 * Mirrors the request/streaming logic already proven out in local_client.py
 * (the Python terminal client) — same endpoints, same NDJSON protocol.
 */

import { expireSession, getToken } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

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
 */
export async function streamMessage(conversationId, audioBlob, handlers = {}) {
  const form = new FormData();
  form.set("conversation_id", conversationId);
  form.set("audio_file", audioBlob, "audio.webm");

  const res = await authFetch(`/api/conversation/message-stream`, {
    method: "POST",
    body: form,
  });

  if (!res.ok || !res.body) {
    const message = await errorMessage(res, "Couldn't send that recording");
    handlers.onError?.(message);
    throw new Error(message);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    // Last element may be a partial line — keep it buffered for the next chunk.
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.trim()) continue;
      let msg;
      try {
        msg = JSON.parse(line);
      } catch {
        continue;
      }
      dispatch(msg, handlers);
    }
  }

  // Flush any trailing line without a final newline.
  if (buffer.trim()) {
    try {
      dispatch(JSON.parse(buffer), handlers);
    } catch {
      /* ignore trailing garbage */
    }
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
