/**
 * Reading a newline-delimited JSON stream (one JSON object per line), which is how the voice loop's reply
 * arrives (see backend/routers/conversation.py): the transcript, the speech metrics, the coach's sentences as
 * audio chunks, then a final "done". It is kept free of `fetch` and of the app's own modules so that the
 * awkward cases (a line split across network chunks, a stream that goes quiet, a caller that gives up) can be
 * unit-tested (lib/ndjson.test.js).
 */

/** The connection is open but nothing has arrived for too long: treat the reply as lost. */
export class StreamStalledError extends Error {
  constructor(message = "The coach stopped responding. Please try again.") {
    super(message);
    this.name = "StreamStalledError";
  }
}

/**
 * Turns text that arrives in arbitrary pieces into JSON messages. A message can straddle two pieces, so the
 * unfinished tail is held until the rest arrives; a line that is not valid JSON is skipped.
 */
export function createLineParser(onMessage) {
  let buffer = "";

  function emit(line) {
    if (!line.trim()) return;
    let message;
    try {
      message = JSON.parse(line);
    } catch {
      return;
    }
    onMessage(message);
  }

  return {
    push(text) {
      buffer += text;
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? ""; // the last piece may be half a line: keep it for the next chunk
      lines.forEach(emit);
    },
    /** The stream is over: a final line with no trailing newline still counts. */
    end() {
      emit(buffer);
      buffer = "";
    },
  };
}

/**
 * Reads every message from a response body, calling `onMessage` for each, and resolves when the stream ends.
 *
 *  - If nothing arrives for `idleMs`, the reader is cancelled and this rejects with StreamStalledError.
 *  - If `signal` aborts, the reader is cancelled and this rejects with the signal's reason (an AbortError).
 *
 * Resolving only means the stream CLOSED; whether the reply was complete (a "done" message arrived) is for the
 * caller to judge.
 */
export async function readEvents(body, { onMessage, signal, idleMs = 45_000 }) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = createLineParser(onMessage);
  const stop = () => reader.cancel(signal?.reason).catch(() => {});
  const aborted = () => signal.reason ?? new DOMException("The request was aborted.", "AbortError");

  // An "abort" event never fires for a signal that was aborted before we listened, so check first.
  if (signal?.aborted) {
    await stop();
    throw aborted();
  }
  signal?.addEventListener("abort", stop, { once: true });

  try {
    while (true) {
      let timer;
      const stalled = new Promise((_, reject) => {
        timer = setTimeout(() => reject(new StreamStalledError()), idleMs);
      });
      let chunk;
      try {
        chunk = await Promise.race([reader.read(), stalled]);
      } finally {
        clearTimeout(timer);
      }
      if (chunk.done) break;
      parser.push(decoder.decode(chunk.value, { stream: true }));
    }
    parser.push(decoder.decode()); // a multi-byte character cut off at the very end
    parser.end();
  } catch (err) {
    await stop();
    throw err;
  } finally {
    signal?.removeEventListener("abort", stop);
  }

  // Cancelling a reader that is waiting makes its read() finish "normally", so an abort has to be reported here.
  if (signal?.aborted) throw aborted();
}
