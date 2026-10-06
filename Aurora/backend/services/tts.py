"""
Text-to-Speech service — Piper TTS.

Piper synthesizes raw PCM audio (16-bit, mono). We wrap it in a WAV container
so the output is compatible with browsers, sounddevice, and standard audio tools.

Voice models are lazy-loaded and cached per model file to avoid re-loading on
every request (each .onnx load takes ~1-2 seconds).

Which voice speaks is decided by backend/personalities.py: a companion has a home
voice (VOICES), and a speaking style with its own accent swaps in a voice of that
accent (voice_for / ACCENT_VOICES). A multi-speaker model, such as the VCTK one, holds
many speakers, so one loaded model serves several accents. There is no second list to
keep in sync: scripts/download_voices.py reads the same source.
"""
import io
import json
import logging
import re
from functools import lru_cache
import threading
import time
import wave
from pathlib import Path

# pyrefly: ignore [missing-import]
import piper

from backend.config import VOICES_DIR
from backend.personalities import DEFAULT_STYLE, STYLES, VOICES, model_files, voice_for

logger = logging.getLogger("aura.tts")

# ── Sentence boundary detection ───────────────────────────────────────────────
# Used by the streaming endpoint to know when a sentence is ready for TTS.
# Hard boundaries (.!?) are always split. Soft boundaries (,;) only if the
# buffer is already long enough to avoid tiny TTS calls.
HARD_BOUNDARY = re.compile(r'[.!?](\s|$)')
SOFT_BOUNDARY = re.compile(r'[,;:](\s|$)')
MIN_CHARS = 45           # Min chars before a hard boundary (.!?) triggers a split.
                         # Keeps short phrases ('Sounds good, thanks!') as one chunk — better prosody.
                         # Only genuinely multi-sentence replies get chunked for streaming.
FIRST_CHUNK_MIN_CHARS = 18  # The FIRST chunk of a reply may be shorter: the learner is waiting in silence
                         # for it, so a brief opener ("Sounds like a busy day!") is spoken as soon as
                         # its sentence ends instead of idling until more text has arrived.
SOFT_MIN_CHARS = 120     # Safety valve: if a sentence has no period for 120+ chars,
                         # split on a comma to prevent hitting Piper's max length limit.


# companion id -> model filename inside the voices directory (derived, not duplicated)
VOICE_FILES: dict[str, str] = {vid: Path(v["file"]).name for vid, v in VOICES.items()}
# every model file the app can use, and the ones only a regional accent needs
ALL_MODEL_FILES: list[str] = [Path(f).name for f in model_files()]
REGIONAL_FILES: list[str] = [f for f in ALL_MODEL_FILES if f not in VOICE_FILES.values()]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def voices_dir() -> Path:
    """The voices directory; a relative VOICES_DIR is resolved against the project root, not the CWD."""
    path = Path(VOICES_DIR)
    return path if path.is_absolute() else _PROJECT_ROOT / path


def model_path(filename: str) -> Path:
    return voices_dir() / filename


def _model_installed(filename: str) -> bool:
    onnx = model_path(filename)
    return onnx.exists() and onnx.with_name(onnx.name + ".json").exists()


def voice_path(voice_id: str) -> Path:
    filename = VOICE_FILES.get(voice_id)
    if not filename:
        raise ValueError(f"Unknown voice_id '{voice_id}'. Valid options: {list(VOICE_FILES)}")
    return model_path(filename)


def voice_available(voice_id: str) -> bool:
    """True when the model file for this companion's own voice is installed on this machine."""
    try:
        return voice_path(voice_id).exists()
    except ValueError:
        return False


def available_voices() -> list[str]:
    return [vid for vid in VOICE_FILES if voice_available(vid)]


def missing_voices() -> list[str]:
    return [vid for vid in VOICE_FILES if not voice_available(vid)]


def missing_regional_models() -> list[str]:
    return [f for f in REGIONAL_FILES if not _model_installed(f)]


@lru_cache(maxsize=None)
def _speaker_names(filename: str) -> frozenset[str]:
    """The speakers a multi-speaker model holds (empty for a single-speaker model)."""
    try:
        with open(model_path(filename).with_name(filename + ".json"), encoding="utf-8") as f:
            return frozenset(json.load(f).get("speaker_id_map", {}))
    except (OSError, ValueError):
        return frozenset()


def style_problem(voice_id: str, style: str) -> str | None:
    """
    Why this companion can't speak this style (None when they can): the style needs an accent the
    companion has no voice for, or the model that holds that voice isn't installed here.
    """
    if voice_id not in VOICES:
        return f"Unknown companion: {voice_id}"
    if style not in STYLES:
        return f"Unknown speaking style: {style}"
    who, what = VOICES[voice_id]["label"], STYLES[style]["label"]
    spec = voice_for(voice_id, style)
    if spec is None:
        return f"{who} doesn't have a voice for {what} yet. Pick another companion or speaking style."
    filename = Path(spec["file"]).name
    if not _model_installed(filename) or (spec["speaker"] is not None and spec["speaker"] not in _speaker_names(filename)):
        return f"The voice {who} uses for {what} isn't installed on this server."
    return None


def style_available(voice_id: str, style: str) -> bool:
    return style_problem(voice_id, style) is None


def status() -> dict:
    """
    What the health check reports: how many companion voices are installed on disk and loaded in memory,
    and whether the extra models that regional accents need are installed.
    """
    return {
        "installed": len(available_voices()),
        "total": len(VOICE_FILES),
        "loaded": sum(1 for f in VOICE_FILES.values() if f in _voice_cache),
        "missing": missing_voices(),
        "regional": {"installed": len(REGIONAL_FILES) - len(missing_regional_models()), "total": len(REGIONAL_FILES)},
    }


# Loaded models, cached by model file: populated on first use
_voice_cache: dict[str, piper.PiperVoice] = {}
_load_lock = threading.Lock()


def _load_model(filename: str, label: str) -> piper.PiperVoice:
    """
    Returns the cached PiperVoice for a model file, loading it on first access. The lock stops the startup
    pre-warm thread and a request from loading the same ~60-120 MB model twice at the same moment.
    """
    cached = _voice_cache.get(filename)
    if cached is not None:
        return cached

    with _load_lock:
        cached = _voice_cache.get(filename)
        if cached is not None:
            return cached

        onnx_path = model_path(filename)
        config_path = onnx_path.with_name(onnx_path.name + ".json")

        if not onnx_path.exists():
            raise FileNotFoundError(
                f"Voice file not found: {onnx_path}\n"
                f"Run: python scripts/download_voices.py"
            )

        logger.info("Loading voice %s (%s)...", label, filename)
        _voice_cache[filename] = piper.PiperVoice.load(
            str(onnx_path),
            config_path=str(config_path) if config_path.exists() else None,
        )
        logger.info("Voice loaded: %s", label)
        return _voice_cache[filename]


def _get_voice(voice_id: str) -> piper.PiperVoice:
    """A companion's own (home) voice."""
    return _load_model(VOICE_FILES[voice_id], voice_id)


def _label_for(voice_id: str, spec: dict) -> str:
    """How a loaded model is named in the log: the companion's id for their own voice, else the model's name."""
    return voice_id if Path(spec["file"]).name == VOICE_FILES.get(voice_id) else Path(spec["file"]).stem


def prewarm() -> None:
    """
    Loads every installed companion voice so the first user turn doesn't pay the .onnx
    load cost. Reports missing voice files loudly instead of failing later,
    mid-conversation, on the first user who picks that companion. The regional accent
    models are not loaded here (they are big and only some sessions need them): a session
    that uses one loads it when it starts (see preload).
    """
    for voice_id in missing_voices():
        logger.error(
            "Voice '%s' is not installed (%s) — it will be hidden from the picker. "
            "Run: python scripts/download_voices.py",
            voice_id, voice_path(voice_id).name,
        )
    missing = missing_regional_models()
    if missing:
        logger.warning(
            "Regional accent voices are missing (%s), so the speaking styles that need them are hidden. "
            "Run: python scripts/download_voices.py",
            ", ".join(missing),
        )
    for voice_id in available_voices():
        try:
            _get_voice(voice_id)
        except Exception:
            logger.exception("Pre-warming voice %s failed (non-fatal)", voice_id)


def preload(voice_id: str, style: str = DEFAULT_STYLE) -> None:
    """
    Loads the model a session will speak with, ahead of its first reply, so the learner doesn't wait for a
    ~2-5 s model load after their first sentence. Best effort: a failure here just means it loads on demand.
    """
    try:
        spec = voice_for(voice_id, style)
        if spec is not None and _model_installed(Path(spec["file"]).name):
            _load_model(Path(spec["file"]).name, _label_for(voice_id, spec))
    except Exception:
        logger.exception("Preloading the voice for %s/%s failed (non-fatal)", voice_id, style)


def synthesize(text: str, voice_id: str = "amy", length_scale: float | None = None, style: str = DEFAULT_STYLE) -> dict:
    """
    Synthesize text to WAV audio bytes.

    Uses piper-tts 1.8.0 API:
        voice.synthesize_wav(text, wav_file) — writes WAV directly to a wave.Wave_write object.

    Args:
        text:         Text to synthesize.
        voice_id:     A key of personalities.VOICES (the companion).
        length_scale: Stretches the speech (1.0 = the voice's normal pace; larger = slower).
        style:        The speaking style: with an accent of its own, it decides which voice the companion uses.

    Returns:
        {
            "audio_bytes": bytes  — complete WAV file ready to play or send
            "latency_ms":  float  — synthesis time in milliseconds
        }
    """
    t0 = time.perf_counter()
    spec = voice_for(voice_id, style)
    if spec is None:
        raise ValueError(f"{voice_id} has no voice for the '{style}' style")
    filename = Path(spec["file"]).name
    voice = _load_model(filename, _label_for(voice_id, spec))

    options: dict = {}
    if spec["speaker"] is not None:             # a multi-speaker model: pick the speaker by name
        speaker_id = voice.config.speaker_id_map.get(spec["speaker"])
        if speaker_id is None:
            raise ValueError(f"The voice file {filename} has no speaker '{spec['speaker']}'")
        options["speaker_id"] = speaker_id
    if length_scale is not None:
        options["length_scale"] = length_scale

    # synthesize_wav() writes directly into a wave.Wave_write object.
    # It also calls set_wav_format() on it automatically (sets channels, rate, width).
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        if options:
            voice.synthesize_wav(text, wf, syn_config=piper.SynthesisConfig(**options))
        else:
            voice.synthesize_wav(text, wf)

    wav_bytes = wav_buffer.getvalue()
    latency_ms = (time.perf_counter() - t0) * 1000

    return {
        "audio_bytes": wav_bytes,
        "latency_ms": round(latency_ms, 1),
    }


def split_sentences(buffer: str, min_chars: int = MIN_CHARS) -> tuple[list[str], str]:
    """
    Extracts complete sentences from a running token buffer.

    Called repeatedly as LLM tokens arrive. Returns all sentences that are
    ready for TTS synthesis, plus whatever remains in the buffer.

    Rules:
    1. Hard boundaries (.!?): always split, as long as fragment >= min_chars.
    2. Soft boundaries (,;): split only if buffer >= SOFT_MIN_CHARS, to avoid
       synthesizing tiny comma-separated fragments.
    3. Minimum length: never yield a sentence shorter than min_chars chars.

    Args:
        buffer:    Accumulated LLM tokens so far (not yet synthesized).
        min_chars: Shortest sentence worth synthesizing on its own. Pass
                   FIRST_CHUNK_MIN_CHARS for the first chunk of a reply.

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
        # Find the first hard boundary that meets the min_chars threshold
        found_cut = -1
        for m in HARD_BOUNDARY.finditer(remainder):
            if m.start() >= min_chars - 1:
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


def synthesize_text(text: str, voice_id: str = "amy", style: str = DEFAULT_STYLE) -> bytes:
    """
    Thin convenience wrapper around synthesize() that returns just the WAV bytes.

    Used by the streaming endpoint where the latency dict is not needed per chunk
    (overall timing is tracked at the endpoint level instead).

    Args:
        text:     Sentence text to synthesize.
        voice_id: A key of personalities.VOICES.
        style:    The session's speaking style (it decides the accent).

    Returns:
        bytes — complete WAV file bytes ready for base64 encoding or playback.
    """
    return synthesize(text, voice_id, style=style)["audio_bytes"]


SLOW_LENGTH_SCALE = 1.7  # "say it slowly": ~70% longer than the voice's normal pace


@lru_cache(maxsize=256)
def word_audio(word: str, voice_id: str, slow: bool = False, style: str = DEFAULT_STYLE) -> bytes:
    """
    One word, spoken on its own (optionally slowly) — for the "hear this word"
    button next to words the learner was hard to understand on. Cached, because
    the same handful of words get requested again and again.
    """
    return synthesize(word, voice_id, SLOW_LENGTH_SCALE if slow else None, style)["audio_bytes"]
