"""
Text-to-Speech service wrapper — Piper TTS.
Phase 0: stub only. Fully implemented in Phase 1.
"""


def synthesize(text: str, voice_id: str) -> bytes:
    """
    Synthesize speech from text.

    Args:
        text:     The text to speak.
        voice_id: One of: amy, alan, ryan, lessac

    Returns:
        Raw PCM audio bytes (16-bit, 16kHz, mono)

    Phase 0: raises NotImplementedError.
    Phase 1: implemented with Piper.
    """
    raise NotImplementedError("TTS service not yet implemented — see Phase 1")
