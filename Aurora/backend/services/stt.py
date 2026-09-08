"""
Speech-to-Text service wrapper — faster-whisper.
Phase 0: stub only. Fully implemented in Phase 1.
"""


def transcribe(audio_path: str) -> dict:
    """
    Transcribe audio file.

    Returns:
        {
            "text": str,
            "words": [{"word": str, "start": float, "end": float, "probability": float}],
            "duration": float,
            "avg_logprob": float,
        }

    Phase 0: raises NotImplementedError.
    Phase 1: implemented with faster-whisper.
    """
    raise NotImplementedError("STT service not yet implemented — see Phase 1")
