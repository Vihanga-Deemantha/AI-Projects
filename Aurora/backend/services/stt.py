"""
Speech-to-text. Two interchangeable providers behind one `transcribe()`:

  local — faster-whisper on this machine's CPU. Private and offline, but it
          slows down sharply when several users talk at once, and base.en
          drops filler words ("um", "uh") and sometimes silently "corrects" a
          learner's grammar, which hides exactly what the coach should see.
  groq  — Groq's hosted Whisper. Keeps fillers, preserves learner errors
          verbatim, and doesn't compete for local CPU. The audio leaves this
          machine (to the same provider already used for the LLM).

Selected with STT_PROVIDER. Both return the same dict, so nothing downstream
cares which one ran. The local model is lazy-loaded on first use (singleton).
"""
import logging
import time
from pathlib import Path

from backend.config import (
    GROQ_STT_MODEL,
    STT_PROVIDER,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_SIZE,
)

logger = logging.getLogger("aura.stt")

_model = None  # faster_whisper.WhisperModel, loaded lazily (local provider only)


class AudioDecodeError(Exception):
    """The input audio can't be demuxed/decoded (corrupt, truncated or too short)."""


class STTUnavailableError(Exception):
    """The recogniser itself failed (rate limit, outage, network) — worth retrying later."""


def provider() -> str:
    return STT_PROVIDER if STT_PROVIDER in ("local", "groq") else "local"


def status() -> dict:
    """What the health check reports: which recogniser is in use and whether it can answer instantly."""
    if provider() == "groq":
        return {"provider": "groq", "ready": True}
    return {"provider": "local", "ready": _model is not None}


def supports_fillers() -> bool:
    """Whether this provider reliably transcribes "um"/"uh" (so filler counts mean something)."""
    return provider() == "groq"


def provides_word_confidence() -> bool:
    """Whether words carry a per-word confidence (needed for the word-level clarity list)."""
    return provider() == "local"


def prewarm() -> None:
    """Loads the local Whisper model now (no-op for the hosted provider)."""
    if provider() != "local":
        return
    try:
        _get_model()
    except Exception:
        logger.exception("Pre-warming Whisper failed (non-fatal; it will load on first use)")


def transcribe(audio_path: str) -> dict:
    """
    Transcribe an audio file to text with word-level timestamps.

    Args:
        audio_path: Absolute path to the audio file (.wav, .webm, .mp3, ...)

    Returns:
        {
            "text":        str    — full transcript
            "duration":    float  — audio length in seconds
            "words":       list   — [{word, start, end, probability|None}, ...] (plain floats)
            "avg_logprob": float  — avg ASR log-probability across segments
            "latency_ms":  float  — time taken to transcribe in ms
        }

    Raises:
        AudioDecodeError:   the audio itself is unusable.
        STTUnavailableError: the recogniser failed for a reason that isn't the audio's fault.
    """
    if provider() == "groq":
        return _transcribe_groq(audio_path)
    return _transcribe_local(audio_path)


# ── Local: faster-whisper ───────────────────────────────────────────────────

def _get_model():
    """
    Returns the shared WhisperModel, loading it on the first call.
    Downloads the model weights (~150MB for base.en) on first run — cached afterward.
    """
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        logger.info("Loading Whisper model %s (%s/%s)...", WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE)
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        logger.info("Whisper model loaded and ready.")
    return _model


def _transcribe_local(audio_path: str) -> dict:
    """
    Notes:
        - word_timestamps=True feeds fluency/clarity analysis.
        - vad_filter=True strips leading/trailing silence, improving accuracy.
        - Forcing language="en" is much faster than auto-detection.
        - Deliberately NO disfluency `initial_prompt`: it recovers "um/uh" but
          makes base.en hallucinate fake "Umm..." sentences on fluent speech.
        - The generator returned by transcribe() is materialised here so callers
          always receive a plain dict, never a lazy iterator.
    """
    model = _get_model()
    t0 = time.perf_counter()

    # faster-whisper decodes the audio via PyAV/ffmpeg under the hood, lazily
    # on first iteration of `segments` (not on the transcribe() call itself).
    # Browser recordings (e.g. Chrome's MediaRecorder webm/opus output) can
    # occasionally be malformed or pathologically short in a way PyAV can't
    # demux — wrap both the call and the iteration so either failure point
    # surfaces a clean, actionable message instead of a raw ffmpeg errno.
    try:
        segments, info = model.transcribe(
            audio_path,
            word_timestamps=True,
            language="en",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300),
        )

        # Materialise the lazy generator — must iterate to get results
        all_words = []
        full_text_parts = []
        total_logprob = 0.0
        segment_count = 0

        for segment in segments:
            text = segment.text.strip()
            if text:
                full_text_parts.append(text)
            total_logprob += float(segment.avg_logprob)
            segment_count += 1

            if segment.words:
                for word in segment.words:
                    # float(): faster-whisper hands back numpy floats, which
                    # str()/json can't round-trip cleanly.
                    all_words.append({
                        "word": word.word.strip(),
                        "start": round(float(word.start), 3),
                        "end": round(float(word.end), 3),
                        "probability": round(float(word.probability), 3),
                    })
    except Exception as exc:
        # Usually a corrupt or pathologically short recording, but ANY failure inside the model
        # lands here. The learner gets the friendly message either way; the log keeps the real
        # cause, because without it a model or out-of-memory failure looks exactly like bad audio.
        logger.warning("Whisper couldn't process a recording: %s", exc, exc_info=True)
        raise AudioDecodeError(
            "Could not process that recording — it may have been too short or corrupted. "
            "Please try again and hold the mic for at least a second."
        ) from exc

    latency_ms = (time.perf_counter() - t0) * 1000
    avg_logprob = (total_logprob / segment_count) if segment_count > 0 else 0.0

    return {
        "text": " ".join(full_text_parts).strip(),
        "duration": round(float(info.duration), 2),
        "words": all_words,
        "avg_logprob": round(avg_logprob, 4),
        "latency_ms": round(latency_ms, 1),
    }


# ── Groq: hosted Whisper ────────────────────────────────────────────────────

# Hosted Whisper has no VAD, so on near-silence it can invent a phrase. A
# segment this sure there is no speech is dropped.
_NO_SPEECH_THRESHOLD = 0.8


def _transcribe_groq(audio_path: str) -> dict:
    # Imported here so the local-only setup never needs the groq package at
    # import time, and so tests can monkeypatch the client cleanly.
    from backend.services import llm

    path = Path(audio_path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise AudioDecodeError("Could not read the uploaded recording.") from exc
    if not data:
        raise AudioDecodeError("The recording was empty. Please try again.")

    t0 = time.perf_counter()
    try:
        result = llm.get_client().audio.transcriptions.create(
            file=(path.name, data),
            model=GROQ_STT_MODEL,
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
            language="en",
            temperature=0.0,
        )
    except Exception as exc:  # groq.* errors; classified by status below
        status = getattr(exc, "status_code", None)
        if status == 400:
            raise AudioDecodeError(
                "Could not process that recording — it may have been too short or corrupted. "
                "Please try again and hold the mic for at least a second."
            ) from exc
        logger.warning("Groq transcription failed (status=%s): %s", status, exc)
        raise STTUnavailableError(
            "Speech recognition is unavailable right now. Please try again in a moment."
        ) from exc

    payload = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    segments = payload.get("segments") or []
    speech_segments = [s for s in segments if (s.get("no_speech_prob") or 0.0) < _NO_SPEECH_THRESHOLD]
    if segments and not speech_segments:
        text = ""
    else:
        text = (payload.get("text") or "").strip()

    words = [
        {
            "word": (w.get("word") or "").strip(),
            "start": round(float(w.get("start", 0.0)), 3),
            "end": round(float(w.get("end", 0.0)), 3),
            "probability": None,  # not provided by the hosted API
        }
        for w in (payload.get("words") or [])
        if (w.get("word") or "").strip()
    ] if text else []

    logprobs = [float(s["avg_logprob"]) for s in speech_segments if s.get("avg_logprob") is not None]
    avg_logprob = (sum(logprobs) / len(logprobs)) if logprobs else 0.0

    return {
        "text": text,
        "duration": round(float(payload.get("duration") or 0.0), 2),
        "words": words,
        "avg_logprob": round(avg_logprob, 4),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
