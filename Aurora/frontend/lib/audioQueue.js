/**
 * Sequential WAV chunk playback via the Web Audio API.
 *
 * Browser analogue of local_client.py's producer-consumer queue+thread
 * pattern: chunks arrive out of order with the network, but must play back
 * strictly in order, one at a time, with no gaps or overlap.
 *
 * Also exposes an AnalyserNode so a waveform visualization can react to
 * whatever is currently playing — the same analyser is reused across chunks
 * rather than recreated per chunk.
 */
export function createAudioQueue({ onChunkStart, onQueueEmpty } = {}) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  analyser.connect(ctx.destination);

  let queue = [];
  let playing = false;
  let userPaused = false; // the learner pressed Pause; nothing but Resume may restart the voice

  function decode(base64Wav) {
    const binary = atob(base64Wav);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return ctx.decodeAudioData(bytes.buffer.slice(0));
  }

  async function playNext() {
    const next = queue.shift();
    if (!next) {
      playing = false;
      onQueueEmpty?.();
      return;
    }
    playing = true;
    try {
      const audioBuffer = await decode(next.base64);
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(analyser);
      source.onended = () => playNext();
      onChunkStart?.(next.text);
      source.start();
    } catch (err) {
      console.error("[audioQueue] failed to decode/play chunk:", err);
      playNext();
    }
  }

  function enqueue(base64Wav, text) {
    queue.push({ base64: base64Wav, text });
    if (!playing) playNext();
  }

  function reset() {
    queue = [];
  }

  function close() {
    reset();
    ctx.close().catch(() => {});
  }

  /** Pauses AURA's voice playback in place (Web Audio has no per-source pause, so we suspend the whole context). */
  function pause() {
    userPaused = true;
    if (ctx.state === "running") ctx.suspend().catch(() => {});
  }

  function resume() {
    userPaused = false;
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
  }

  /**
   * Lets the voice play. Call it from inside a press or key event: Safari only starts audio that a user
   * gesture asked for, and the first reply arrives long after the gesture, so the context has to be woken
   * by the press that began the turn. It never overrides the learner's own Pause.
   */
  function unlock() {
    if (!userPaused && ctx.state === "suspended") ctx.resume().catch(() => {});
  }

  return {
    enqueue,
    reset,
    close,
    pause,
    resume,
    unlock,
    analyser,
    get isPlaying() {
      return playing;
    },
    get isSuspended() {
      return ctx.state === "suspended";
    },
  };
}
