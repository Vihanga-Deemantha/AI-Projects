"""
Speech helper endpoints.

POST /api/speech/word — a single word, spoken by a companion's voice (optionally
slowly). Powers the "hear it" buttons next to the words a learner was hardest to
understand on, so they can hear how the word should sound. Pass the session's speaking
style and the word is said in that session's accent.
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from backend.dependencies import get_current_user
from backend.models.core import User
from backend.personalities import DEFAULT_STYLE, DEFAULT_VOICE, STYLES, VOICES
from backend.services import tts
from backend.services.ratelimit import WORD_AUDIO_PER_USER, enforce

router = APIRouter(prefix="/api/speech", tags=["speech"])


class WordAudioRequest(BaseModel):
    # One word: letters, with apostrophes/hyphens inside ("don't", "well-known").
    word: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z][A-Za-z'\-]*$")
    voice: str | None = Field(default=None, max_length=50)
    style: str | None = Field(default=None, max_length=50)
    slow: bool = False


@router.post("/word", response_class=Response, responses={200: {"content": {"audio/wav": {}}}})
async def word_audio(payload: WordAudioRequest, user: User = Depends(get_current_user)):
    enforce("word:user", user.id, WORD_AUDIO_PER_USER, "You're asking for words too quickly. Please wait a moment.")

    voice = payload.voice or user.preferred_voice or DEFAULT_VOICE
    if voice not in VOICES:
        raise HTTPException(status_code=400, detail=f"Unknown voice: {voice}")
    if not tts.voice_available(voice):
        raise HTTPException(status_code=400, detail=f"The voice '{voice}' isn't installed on this server")

    style = payload.style or user.preferred_style or DEFAULT_STYLE
    if style not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown speaking style: {style}")
    if not tts.style_available(voice, style):
        style = DEFAULT_STYLE        # this companion has no voice for that accent: they say it in their own voice

    try:
        wav = await asyncio.to_thread(tts.word_audio, payload.word.lower(), voice, payload.slow, style)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Couldn't generate that word right now.") from exc

    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"Cache-Control": "private, max-age=86400"},
    )
