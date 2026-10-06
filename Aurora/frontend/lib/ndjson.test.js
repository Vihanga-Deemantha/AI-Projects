import assert from "node:assert/strict";
import { test } from "node:test";
import { createLineParser, readEvents, StreamStalledError } from "./ndjson.js";

const encoder = new TextEncoder();

/** A response body that hands out the given chunks (strings or bytes), then stays open or closes. */
function bodyOf(chunks, { close = true } = {}) {
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(typeof c === "string" ? encoder.encode(c) : c);
      if (close) controller.close();
    },
  });
}

function collect() {
  const messages = [];
  return { messages, onMessage: (m) => messages.push(m) };
}

test("the parser emits one message per line, even when a line is split across pieces", () => {
  const { messages, onMessage } = collect();
  const parser = createLineParser(onMessage);
  parser.push('{"type":"transcript","te');
  parser.push('xt":"hi"}\n{"type":"done"}\n');
  assert.deepEqual(messages, [{ type: "transcript", text: "hi" }, { type: "done" }]);
});

test("the parser keeps a last line that has no trailing newline, and skips lines that are not JSON", () => {
  const { messages, onMessage } = collect();
  const parser = createLineParser(onMessage);
  parser.push('not json\n\n{"type":"warning"}\n{"type":"done"}');
  assert.deepEqual(messages, [{ type: "warning" }]); // the last line is still waiting for its newline
  parser.end();
  assert.deepEqual(messages, [{ type: "warning" }, { type: "done" }]);
});

test("readEvents reads every message, including one whose multi-byte character is cut between chunks", async () => {
  const bytes = encoder.encode('{"type":"transcript","text":"café"}\n{"type":"done"}\n');
  const cut = bytes.indexOf(0xc3) + 1; // between the two bytes of "é"
  const { messages, onMessage } = collect();
  await readEvents(bodyOf([bytes.slice(0, cut), bytes.slice(cut)]), { onMessage });
  assert.deepEqual(messages, [{ type: "transcript", text: "café" }, { type: "done" }]);
});

test("readEvents resolves when the stream ends, whether or not a done message arrived", async () => {
  const { messages, onMessage } = collect();
  await readEvents(bodyOf(['{"type":"transcript","text":"hello"}\n']), { onMessage });
  assert.deepEqual(messages.map((m) => m.type), ["transcript"]); // no "done": the caller can tell the reply was cut short
});

test("a stream that goes quiet is cut off with StreamStalledError", async () => {
  const { messages, onMessage } = collect();
  const started = Date.now();
  await assert.rejects(
    readEvents(bodyOf(['{"type":"transcript","text":"hello"}\n'], { close: false }), { onMessage, idleMs: 40 }),
    (err) => err instanceof StreamStalledError,
  );
  assert.deepEqual(messages.map((m) => m.type), ["transcript"]); // what arrived before the silence was delivered
  assert.ok(Date.now() - started < 2_000);
});

test("a caller that gives up (the learner left the page) stops the read with the abort reason", async () => {
  const controller = new AbortController();
  const { onMessage } = collect();
  const reading = readEvents(bodyOf(['{"type":"transcript"}\n'], { close: false }), { onMessage, signal: controller.signal, idleMs: 5_000 });
  setTimeout(() => controller.abort(new DOMException("Left the page", "AbortError")), 20);
  await assert.rejects(reading, (err) => err.name === "AbortError");
});

test("an already-aborted signal stops immediately", async () => {
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(readEvents(bodyOf([], { close: false }), { onMessage: () => {}, signal: controller.signal, idleMs: 5_000 }), (err) => err.name === "AbortError");
});
