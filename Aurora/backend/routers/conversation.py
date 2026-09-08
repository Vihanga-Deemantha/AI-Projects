"""
Conversation API endpoints.

POST /api/conversation/start   — create a new session record in the DB
POST /api/conversation/message — the core voice loop (audio in, audio out)
"""
import asyncio
import base64
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.core import Conversation, Message, User
from backend.personalities import (
    DEFAULT_SCENARIO,
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    build_system_prompt,
)
from backend.services import llm, stt, tts

router = APIRouter(prefix="/api/conversation", tags=["conversation"])


# ── Start Session ─────────────────────────────────────────────────────────────

@router.post("/start")
def start_conversation(
    user_id: str = Form(...),
    scenario: str = Form(default=DEFAULT_SCENARIO),
    style: str = Form(default=DEFAULT_STYLE),
    voice: str = Form(default=DEFAULT_VOICE),
    db: Session = Depends(get_db),
):
    """
    Creates a new conversation session in the database.
    Returns the conversation_id to use in all subsequent /message calls.
    """
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        user = User(id=user_id)
        db.add(user)
        db.commit()

    conversation = Conversation(
        user_id=user_id,
        scenario=scenario,
        style=style,
        voice=voice,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return {
        "conversation_id": conversation.id,
        "user_id": user_id,
        "scenario": scenario,
        "style": style,
        "voice": voice,
    }


# ── Core Voice Loop ────────────────────────────────────────────────────────────

@router.post("/message")
async def send_message(
    conversation_id: str = Form(...),
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    The core AURA conversation loop.

    IMPORTANT: stt.transcribe(), llm.chat(), and tts.synthesize() are all
    synchronous blocking calls (CPU-bound or network I/O). Running them
    directly in an async function would freeze the entire FastAPI event loop.
    We use asyncio.to_thread() to run each in the thread pool, keeping the
    event loop free to handle other requests while these execute.
    """
    t_total = time.perf_counter()
    timings: dict[str, float] = {}

    # ── Fetch conversation ────────────────────────────────────────────────────
    conversation = db.query(Conversation).filter_by(id=conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")

    # ── Save audio to temp file ───────────────────────────────────────────────
    suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio_file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # ── STT (run in thread — CPU-bound, blocks event loop otherwise) ──────────
    try:
        stt_result = await asyncio.to_thread(stt.transcribe, tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT error: {e}")

    timings["stt_ms"] = stt_result["latency_ms"]
    transcript = stt_result["text"].strip()

    if not transcript:
        return {"error": "No speech detected in audio", "timings": timings}

    # ── Save user message to DB ───────────────────────────────────────────────
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=transcript,
        audio_duration_seconds=stt_result["duration"],
        word_timestamps_json=str(stt_result["words"]),
        whisper_avg_logprob=stt_result["avg_logprob"],
    )
    db.add(user_msg)
    db.commit()

    # ── Build LLM context ─────────────────────────────────────────────────────
    history_rows = (
        db.query(Message)
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at.asc())
        .limit(10)
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in history_rows]

    system_prompt = build_system_prompt(
        scenario=conversation.scenario,
        style=conversation.style,
    )
    messages = llm.build_messages(system_prompt, history)

    # ── LLM (run in thread — network I/O, but Groq client is sync) ───────────
    t0 = time.perf_counter()
    try:
        reply_text = await asyncio.to_thread(llm.chat, messages, None, 0.8, 150)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")
    timings["llm_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    # ── Save assistant message to DB ──────────────────────────────────────────
    assistant_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=reply_text,
    )
    db.add(assistant_msg)
    db.commit()

    # ── TTS (run in thread — CPU-bound, blocks event loop otherwise) ──────────
    try:
        tts_result = await asyncio.to_thread(tts.synthesize, reply_text, conversation.voice)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")
    timings["tts_ms"] = tts_result["latency_ms"]

    # ── Encode audio for JSON transport ───────────────────────────────────────
    audio_b64 = base64.b64encode(tts_result["audio_bytes"]).decode("utf-8")
    timings["total_ms"] = round((time.perf_counter() - t_total) * 1000, 1)

    return {
        "transcript": transcript,
        "reply_text": reply_text,
        "reply_audio_b64": audio_b64,
        "timings": timings,
    }

