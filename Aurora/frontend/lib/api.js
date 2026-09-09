/**
 * AURA backend API client.
 *
 * Mirrors the request/streaming logic already proven out in local_client.py
 * (the Python terminal client) — same endpoints, same NDJSON protocol.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

/** Fetches voice/style/scenario options for the session setup picker. */
export async function getOptions() {
  const res = await fetch(`${API_BASE}/api/config/options`);
  if (!res.ok) throw new Error(`Failed to load options (${res.status})`);
  return res.json();
}

/** Creates a new conversation session. Returns { conversation_id, user_id, scenario, style, voice }. */
export async function startSession({ userId, scenario, style, voice }) {
  const form = new FormData();
  form.set("user_id", userId);
  form.set("scenario", scenario);
  form.set("style", style);
  form.set("voice", voice);

  const res = await fetch(`${API_BASE}/api/conversation/start`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Failed to start session (${res.status})`);
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

  const res = await fetch(`${API_BASE}/api/conversation/message-stream`, {
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
  const res = await fetch(
    `${API_BASE}/api/analysis/conversation/${conversationId}/recent?limit=${limit}`
  );
  if (!res.ok) throw new Error(`Failed to fetch corrections (${res.status})`);
  return res.json();
}
