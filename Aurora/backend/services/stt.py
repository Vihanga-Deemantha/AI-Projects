"""
Speech-to-Text service — faster-whisper.

Model is lazy-loaded on the first call to avoid slowing down FastAPI startup.
The same model instance is reused for all subsequent requests (singleton pattern).
"""
import time
from typing import Optional

from faster_whisper import WhisperModel

from backend.config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL_SIZE

_model: Optional[WhisperModel] = None


class AudioDecodeError(Exception):
    """Raised when the input audio can't be demuxed/decoded (corrupt or malformed file)."""


def _get_model() -> WhisperModel:
    """
    Returns the shared WhisperModel, loading it on the first call.
    Downloads the model weights (~150MB for base.en) on first run — cached afterward.
    """
    global _model
    if _model is None:
        print(
            f"[STT] Loading Whisper model: {WHISPER_MODEL_SIZE} "
            f"({WHISPER_DEVICE}/{WHISPER_COMPUTE_TYPE})..."
        )
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        print("[STT] Model loaded and ready.")
    return _model


def transcribe(audio_path: str) -> dict:
    """
    Transcribe an audio file to text with word-level timestamps.

    Args:
        audio_path: Absolute path to the audio file (.wav, .mp3, etc.)

    Returns:
        {
            "text":        str    — full transcript
            "duration":    float  — audio length in seconds
            "words":       list   — [{word, start, end, probability}, ...]
            "avg_logprob": float  — avg ASR log-probability (pronunciation proxy)
            "latency_ms":  float  — time taken to transcribe in ms
        }

    Notes:
        - word_timestamps=True is required for Phase 4 (fluency analysis).
        - vad_filter=True strips leading/trailing silence, improving accuracy.
        - Forcing language="en" is much faster than auto-detection.
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
            total_logprob += segment.avg_logprob
            segment_count += 1

            if segment.words:
                for word in segment.words:
                    all_words.append({
                        "word": word.word,
                        "start": round(word.start, 3),
                        "end": round(word.end, 3),
                        "probability": round(word.probability, 3),
                    })
    except Exception as exc:
        raise AudioDecodeError(
            "Could not process that recording — it may have been too short or corrupted. "
            "Please try again and hold the mic for at least a second."
        ) from exc

    latency_ms = (time.perf_counter() - t0) * 1000
    avg_logprob = (total_logprob / segment_count) if segment_count > 0 else 0.0

    return {
        "text": " ".join(full_text_parts).strip(),
        "duration": round(info.duration, 2),
        "words": all_words,
        "avg_logprob": round(avg_logprob, 4),
        "latency_ms": round(latency_ms, 1),
    }
