"""
Conversation API endpoints.

POST /api/conversation/start        — create a new session record in the DB
POST /api/conversation/message      — the core voice loop (audio in, audio out), batch
POST /api/conversation/message-stream — streaming voice loop, NDJSON response
"""
import asyncio
import base64
import json
import queue as queue_module
import tempfile
import threading
import time
from pathlib import Path

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
# pyrefly: ignore [missing-import]
from fastapi.responses import StreamingResponse
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.core import Conversation, Message, User
from backend.services.analysis import run_async_analysis
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


# ── Core Voice Loop (batch) ────────────────────────────────────────────────────

@router.post("/message")
async def send_message(
    conversation_id: str = Form(...),
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Batch version: waits for full LLM reply and full TTS before returning.
    Kept as a backward-compatible fallback — use /message-stream for lower latency.

    IMPORTANT: stt.transcribe(), llm.chat(), and tts.synthesize() are all
    synchronous blocking calls. We use asyncio.to_thread() to run each in the
    thread pool, keeping the event loop free.
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

    # ── STT ───────────────────────────────────────────────────────────────────
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

    # ── LLM ───────────────────────────────────────────────────────────────────
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

    # ── TTS ───────────────────────────────────────────────────────────────────
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


# ── Streaming Voice Loop ──────────────────────────────────────────────────────

@router.post("/message-stream")
async def send_message_stream(
    conversation_id: str = Form(...),
    audio_file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """
    Streaming version of /message. Returns NDJSON lines:
        {"type": "transcript", "text": "..."}
        {"type": "audio_chunk", "index": N, "text": "...", "data": "<b64 WAV>", "tts_ms": N}
        {"type": "done", "full_reply": "...", "timings": {...}}
        {"type": "error", "message": "..."}

    CRITICAL: Every code path MUST end with a {"type": "done"} line.
    Without it the HTTP chunked stream never sends the final 0-byte terminator,
    and the client raises ChunkedEncodingError.

    The outer generate() wraps _stream() in a try/except so that even completely
    unexpected exceptions produce a clean done line rather than dropping the
    TCP connection mid-stream.
    """
    t_total = time.perf_counter()
    timings: dict = {}

    # ── Fetch conversation ────────────────────────────────────────────────────
    conversation = db.query(Conversation).filter_by(id=conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # ── Save audio to temp file ───────────────────────────────────────────────
    suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio_file.read())
        tmp_path = tmp.name

    # ─────────────────────────────────────────────────────────────────────────
    async def _stream():
        """
        Inner generator — all real logic lives here.
        generate() wraps this so any exception still produces a clean done line.
        """
        # ── STT ───────────────────────────────────────────────────────────────
        try:
            stt_result = await asyncio.to_thread(stt.transcribe, tmp_path)
        except Exception as e:
            yield json.dumps({"type": "error", "message": f"STT error: {e}"}) + "\n"
            yield json.dumps({"type": "done", "full_reply": "", "timings": timings}) + "\n"
            return

        timings["stt_ms"] = stt_result["latency_ms"]
        transcript = stt_result["text"].strip()

        if not transcript:
            yield json.dumps({"type": "error", "message": "No speech detected"}) + "\n"
            yield json.dumps({"type": "done", "full_reply": "", "timings": timings}) + "\n"
            return

        # ── Send transcript immediately ───────────────────────────────────────
        yield json.dumps({"type": "transcript", "text": transcript}) + "\n"

        # ── Save user message to DB ───────────────────────────────────────────
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

        # ── Spawn async grammar/vocab analysis ────────────────────────────────
        background_tasks.add_task(
            run_async_analysis,
            transcript=transcript,
            message_id=user_msg.id,
            conversation_id=conversation_id,
            user_id=conversation.user_id,
        )

        # ── Build LLM context ─────────────────────────────────────────────────
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
        messages_list = llm.build_messages(system_prompt, history)

        # ── LLM streaming + sentence-chunked TTS ─────────────────────────────
        t_llm_start = time.perf_counter()
        timings["llm_ttfs_ms"] = None

        token_buffer = ""
        full_reply_parts: list[str] = []
        chunk_index = 0
        llm_error: str | None = None

        # Bridge sync LLM generator → async via a thread + Queue
        token_queue: queue_module.Queue = queue_module.Queue()
        SENTINEL = object()

        def stream_tokens():
            try:
                for token in llm.chat_stream(messages_list, max_tokens=400):
                    token_queue.put(token)
            except Exception as exc:
                token_queue.put(Exception(f"LLM error: {exc}"))
            finally:
                token_queue.put(SENTINEL)

        thread = threading.Thread(target=stream_tokens, daemon=True)
        thread.start()

        # Drain tokens
        while True:
            try:
                item = await asyncio.to_thread(token_queue.get, True, 30.0)
            except queue_module.Empty:
                break  # timeout — treat as end of stream

            if item is SENTINEL:
                break

            if isinstance(item, Exception):
                llm_error = str(item)
                break

            token_buffer += str(item)
            sentences, token_buffer = tts.split_sentences(token_buffer)

            for sentence in sentences:
                # Record time to first sentence
                if timings["llm_ttfs_ms"] is None:
                    timings["llm_ttfs_ms"] = round(
                        (time.perf_counter() - t_llm_start) * 1000, 1
                    )

                # Synthesize sentence
                t_tts = time.perf_counter()
                try:
                    wav_bytes = await asyncio.to_thread(
                        tts.synthesize_text, sentence, conversation.voice
                    )
                except Exception as tts_e:
                    print(f"[TTS] Skipping sentence: {tts_e}")
                    full_reply_parts.append(sentence)
                    continue

                tts_ms = round((time.perf_counter() - t_tts) * 1000, 1)
                audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
                full_reply_parts.append(sentence)

                yield json.dumps({
                    "type": "audio_chunk",
                    "index": chunk_index,
                    "text": sentence,
                    "data": audio_b64,
                    "tts_ms": tts_ms,
                }) + "\n"
                chunk_index += 1

        # Report LLM error cleanly and exit
        if llm_error:
            yield json.dumps({"type": "error", "message": llm_error}) + "\n"
            timings["total_ms"] = round((time.perf_counter() - t_total) * 1000, 1)
            yield json.dumps({"type": "done", "full_reply": "", "timings": timings}) + "\n"
            return

        # Flush remaining buffer (sentence without terminal punctuation)
        if token_buffer.strip() and len(token_buffer.strip()) >= 3:
            flush_text = token_buffer.strip()
            t_tts_flush = time.perf_counter()

            # Set llm_ttfs_ms NOW — before TTS — so it's always captured even on failure
            if timings["llm_ttfs_ms"] is None:
                timings["llm_ttfs_ms"] = round(
                    (time.perf_counter() - t_llm_start) * 1000, 1
                )

            try:
                wav_bytes = await asyncio.to_thread(
                    tts.synthesize_text, flush_text, conversation.voice
                )
                tts_ms = round((time.perf_counter() - t_tts_flush) * 1000, 1)
                audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
                full_reply_parts.append(flush_text)
                yield json.dumps({
                    "type": "audio_chunk",
                    "index": chunk_index,
                    "text": flush_text,
                    "data": audio_b64,
                    "tts_ms": tts_ms,
                }) + "\n"
            except Exception as tts_e:
                # Surface TTS failure to client (was silently going to server logs only)
                err_msg = f"TTS failed for flush '{flush_text[:30]}': {tts_e}"
                print(f"[TTS] {err_msg}")
                yield json.dumps({"type": "error", "message": err_msg}) + "\n"
                full_reply_parts.append(flush_text)

        # ── Save assistant message to DB ──────────────────────────────────────
        full_reply = " ".join(full_reply_parts)
        if full_reply:
            assistant_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_reply,
            )
            db.add(assistant_msg)
            db.commit()

        timings["total_ms"] = round((time.perf_counter() - t_total) * 1000, 1)
        yield json.dumps({
            "type": "done",
            "full_reply": full_reply,
            "timings": timings,
        }) + "\n"


    # ─────────────────────────────────────────────────────────────────────────
    async def generate():
        """
        Safety wrapper: catches any exception that escapes _stream() and
        emits a clean error + done so the HTTP chunked stream always terminates
        properly (avoids ChunkedEncodingError on the client).
        """
        try:
            async for chunk in _stream():
                yield chunk
        except Exception as exc:
            yield json.dumps({"type": "error", "message": f"Server error: {exc}"}) + "\n"
            yield json.dumps({"type": "done", "full_reply": "", "timings": timings}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
