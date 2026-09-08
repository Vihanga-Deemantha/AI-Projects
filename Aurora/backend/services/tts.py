"""
Text-to-Speech service — Piper TTS.

Piper synthesizes raw PCM audio (16-bit, mono). We wrap it in a WAV container
so the output is compatible with browsers, sounddevice, and standard audio tools.

Voice models are lazy-loaded and cached per voice_id to avoid re-loading on
every request (each .onnx load takes ~1-2 seconds).
"""
import io
import time
import wave
from pathlib import Path
from typing import Optional

# pyrefly: ignore [missing-import]
import piper

from backend.config import VOICES_DIR

# Map of voice IDs to their .onnx filenames in the voices/ directory
VOICE_FILES: dict[str, str] = {
    "amy":    "en_US-amy-medium.onnx",
    "ryan":   "en_US-ryan-high.onnx",
    "alan":   "en_GB-alan-medium.onnx",
    "lessac": "en_US-lessac-medium.onnx",
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

