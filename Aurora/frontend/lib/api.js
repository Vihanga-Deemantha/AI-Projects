/**
 * AURA backend API client.
 *
 * Mirrors the request/streaming logic already proven out in local_client.py
 * (the Python terminal client) — same endpoints, same NDJSON protocol.
 */

import { getToken, logout } from "@/lib/auth";

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
async function authFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: authHeaders(options.headers),
  });
  if (res.status === 401) {
    logout();
    throw new UnauthorizedError();
  }
  return res;
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
export async function startSession({ scenario, style, voice }) {
  const form = new FormData();
  form.set("scenario", scenario);
  form.set("style", style);
  form.set("voice", voice);

  const res = await authFetch(`/api/conversation/start`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Failed to start session (${res.status})`);
  return res.json();
}

/** Marks a session complete so it gets a duration in history. */
export async function endSession(conversationId) {
  const res = await authFetch(`/api/conversation/${conversationId}/end`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to end session (${res.status})`);
  return res.json();
}

/** Past sessions for the logged-in user, newest first. */
export async function getSessions({ limit = 20, offset = 0 } = {}) {
  const res = await authFetch(`/api/history/sessions?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(`Failed to load history (${res.status})`);
  return res.json();
}

/** One past session: full transcript with corrections attached per turn. */
export async function getSession(conversationId) {
  const res = await authFetch(`/api/history/sessions/${conversationId}`);
  if (res.status === 404) throw new Error("Session not found");
  if (!res.ok) throw new Error(`Failed to load session (${res.status})`);
  return res.json();
}

/**
 * Sends a recorded audio blob to the streaming endpoint and invokes callbacks
 * as NDJSON lines arrive. Browser equivalent of local_client.py's
 * `send_audio_streaming()` — same message types, same handling.
 *
 * Message types from the server:
 *   { type: "transcript", text }
 *   { type: "audio_chunk", index, text, data (b64 wav), tts_ms }
 *   { type: "done", full_reply, timings }
 *   { type: "error", message }
 *
 * @param {string} conversationId
 * @param {Blob} audioBlob
 * @param {{
 *   onTranscript?: (text: string) => void,
 *   onAudioChunk?: (chunk: {index:number, text:string, data:string, tts_ms:number}) => void,
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
    const message = `Stream request failed (${res.status})`;
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
      handlers.onTranscript?.(msg.text);
      break;
    case "audio_chunk":
      handlers.onAudioChunk?.(msg);
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

/** Fetches recent grammar/vocab corrections for a conversation (Option B — polled after the fact). */
export async function getRecentCorrections(conversationId, limit = 5) {
  const res = await authFetch(
    `/api/analysis/conversation/${conversationId}/recent?limit=${limit}`
  );
  if (!res.ok) throw new Error(`Failed to fetch corrections (${res.status})`);
  return res.json();
}
