"""
Text-to-Speech service — Piper TTS.

Piper synthesizes raw PCM audio (16-bit, mono). We wrap it in a WAV container
so the output is compatible with browsers, sounddevice, and standard audio tools.

Voice models are lazy-loaded and cached per voice_id to avoid re-loading on
every request (each .onnx load takes ~1-2 seconds).
"""
import io
import re
import time
import wave
from pathlib import Path
from typing import Optional

# pyrefly: ignore [missing-import]
import piper

from backend.config import VOICES_DIR

# ── Sentence boundary detection ───────────────────────────────────────────────
# Used by the streaming endpoint to know when a sentence is ready for TTS.
# Hard boundaries (.!?) are always split. Soft boundaries (,;) only if the
# buffer is already long enough to avoid tiny TTS calls.
HARD_BOUNDARY = re.compile(r'[.!?](\s|$)')
SOFT_BOUNDARY = re.compile(r'[,;:](\s|$)')
MIN_CHARS = 45           # Min chars before a hard boundary (.!?) triggers a split.
                         # Keeps short phrases ('Ahoy, mate!') as one chunk — better prosody.
                         # Only genuinely multi-sentence replies get chunked for streaming.
SOFT_MIN_CHARS = 120     # Safety valve: if a sentence has no period for 120+ chars,
                         # split on a comma to prevent hitting Piper's max length limit.


# Map of voice IDs to their .onnx filenames in the voices/ directory
VOICE_FILES: dict[str, str] = {
    "amy":    "en_US-amy-medium.onnx",   # 60 MB  — female, American (friendly)
    "ryan":   "en_US-ryan-high.onnx",    # 115 MB — male, American (high quality)
    "alan":   "en_GB-alan-medium.onnx",  # 60 MB  — male, British (professional)
    "lessac": "en_US-lessac-medium.onnx",# 60 MB  — female, American (energetic)
}


# Cached voice instances — populated on first use per voice_id
_voice_cache: dict[str, piper.PiperVoice] = {}


def _get_voice(voice_id: str) -> piper.PiperVoice:
    """
    Returns a cached PiperVoice for the given voice_id.
    Loads from disk on first access (lazy singleton per voice).
    """
    if voice_id not in _voice_cache:
        voices_dir = Path(VOICES_DIR)
        filename = VOICE_FILES.get(voice_id)

        if not filename:
            raise ValueError(
                f"Unknown voice_id '{voice_id}'. "
                f"Valid options: {list(VOICE_FILES.keys())}"
            )

        onnx_path = voices_dir / filename
        config_path = voices_dir / (filename + ".json")

        if not onnx_path.exists():
            raise FileNotFoundError(
                f"Voice file not found: {onnx_path}\n"
                f"Make sure the voices/ directory contains the .onnx files."
            )

        print(f"[TTS] Loading voice: {voice_id} ({filename})...")
        _voice_cache[voice_id] = piper.PiperVoice.load(
            str(onnx_path),
            config_path=str(config_path) if config_path.exists() else None,
        )
        print(f"[TTS] Voice loaded: {voice_id}")

    return _voice_cache[voice_id]


def synthesize(text: str, voice_id: str = "amy") -> dict:
    """
    Synthesize text to WAV audio bytes.

    Uses piper-tts 1.8.0 API:
        voice.synthesize_wav(text, wav_file) — writes WAV directly to a wave.Wave_write object.

    Args:
        text:     Text to synthesize.
        voice_id: One of: amy, ryan, alan, lessac

    Returns:
        {
            "audio_bytes": bytes  — complete WAV file ready to play or send
            "latency_ms":  float  — synthesis time in milliseconds
        }
    """
    t0 = time.perf_counter()
    voice = _get_voice(voice_id)

    # synthesize_wav() writes directly into a wave.Wave_write object.
    # It also calls set_wav_format() on it automatically (sets channels, rate, width).
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        voice.synthesize_wav(text, wf)

    wav_bytes = wav_buffer.getvalue()
    latency_ms = (time.perf_counter() - t0) * 1000

    return {
        "audio_bytes": wav_bytes,
        "latency_ms": round(latency_ms, 1),
    }


def split_sentences(buffer: str) -> tuple[list[str], str]:
    """
    Extracts complete sentences from a running token buffer.

    Called repeatedly as LLM tokens arrive. Returns all sentences that are
    ready for TTS synthesis, plus whatever remains in the buffer.

    Rules:
    1. Hard boundaries (.!?): always split, as long as fragment >= MIN_CHARS.
    2. Soft boundaries (,;): split only if buffer >= SOFT_MIN_CHARS, to avoid
       synthesizing tiny comma-separated fragments.
    3. Minimum length: never yield a sentence shorter than MIN_CHARS chars.

    Args:
        buffer: Accumulated LLM tokens so far (not yet synthesized).

    Returns:
        sentences: List of complete sentence strings ready for TTS.
        remainder: Remaining buffer content (the start of the next sentence).

    Example:
        buffer = "Hello! That sounds great. Tell me"
        sentences, remainder = split_sentences(buffer)
        # sentences = ["Hello!", "That sounds great."]
        # remainder = "Tell me"
    """
    sentences = []
    remainder = buffer

    while True:
        # Find the first hard boundary that meets the MIN_CHARS threshold
        found_cut = -1
        for m in HARD_BOUNDARY.finditer(remainder):
            if m.start() >= MIN_CHARS - 1:
                found_cut = m.start() + 1  # include the punctuation itself
                break
                
        if found_cut != -1:
            sentence = remainder[:found_cut].strip()
            if sentence:
                sentences.append(sentence)
            remainder = remainder[found_cut:].lstrip()
            continue

        # Soft boundary: ,;: — only if buffer is getting dangerously long
        found_soft = -1
        for m in SOFT_BOUNDARY.finditer(remainder):
            if m.start() >= SOFT_MIN_CHARS - 1:
                found_soft = m.start() + 1
                break
                
        if found_soft != -1:
            sentence = remainder[:found_soft].strip()
            if sentence:
                sentences.append(sentence)
            remainder = remainder[found_soft:].lstrip()
            continue

        break  # No valid boundaries found

    return sentences, remainder


def synthesize_text(text: str, voice_id: str = "amy") -> bytes:
    """
    Thin convenience wrapper around synthesize() that returns just the WAV bytes.

    Used by the streaming endpoint where the latency dict is not needed per chunk
    (overall timing is tracked at the endpoint level instead).

    Args:
        text:     Sentence text to synthesize.
        voice_id: Piper voice ID (amy, ryan, alan, lessac).

    Returns:
        bytes — complete WAV file bytes ready for base64 encoding or playback.
    """
    return synthesize(text, voice_id)["audio_bytes"]
