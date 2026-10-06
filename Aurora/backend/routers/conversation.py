"""
Conversation API endpoints.

POST /api/conversation/start           — create a new session record in the DB
POST /api/conversation/{id}/end        — close a session
POST /api/conversation/message-stream  — the voice loop (audio in, NDJSON out)

The voice loop streams newline-delimited JSON events:
    {"type": "transcript",  "text": "...", "message_id": "..."}
    {"type": "metrics",     "message_id": "...", "fluency": {...} | null}   (how they spoke)
    {"type": "audio_chunk", "index": N, "text": "...", "data": "<b64 WAV>", "tts_ms": N}
    {"type": "warning",     "message": "..."}      (non-fatal, e.g. one sentence couldn't be spoken)
    {"type": "error",       "message": "..."}
    {"type": "done",        "full_reply": "...", "timings": {...}}

CRITICAL: every code path MUST end with a {"type": "done"} line. Without it the
chunked HTTP stream never sends its final terminator and the client hangs.
"""
import asyncio
import base64
import json
import logging
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
# pyrefly: ignore [missing-import]
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
# pyrefly: ignore [missing-import]
from sqlalchemy import func
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from backend import taxonomy
from backend.config import MAX_AUDIO_BYTES, MAX_AUDIO_SECONDS
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.core import Conversation, Message, User
from backend.personalities import (
    DEFAULT_SCENARIO,
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    SCENARIOS,
    STYLES,
    VOICES,
    build_system_prompt,
)
from backend.services import background, difficulty, llm, reports, speech_metrics, stt, tts, turns
from backend.services.analysis import run_async_analysis
from backend.services.ratelimit import VOICE_TURN_PER_USER, enforce

logger = logging.getLogger("aura.conversation")

router = APIRouter(prefix="/api/conversation", tags=["conversation"])

# No LLM token for this long means the provider has stalled.
LLM_TOKEN_TIMEOUT_SECONDS = 30.0
_ALLOWED_AUDIO_SUFFIXES = {".webm", ".wav", ".ogg", ".mp3", ".m4a", ".mp4", ".flac"}

# A session that has been quiet for longer than this when it is ended (a learner who walked away and came
# back, or who finishes it later from History) is closed where its last message left off, not at "now".
# The time in between was not practice, and counting it would stretch the session's length, move it to the
# wrong day for streaks and inflate the practice time on the progress page.
IDLE_AFTER_LAST_MESSAGE = timedelta(minutes=30)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _owned_conversation(conversation_id: str, user: User, db: Session) -> Conversation:
    """
    Loads a conversation, or 404s unless it belongs to `user`.

    Deliberately 404 (not 403) for someone else's conversation: a 403 would
    confirm the id exists, letting ids be enumerated.
    """
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _event(**fields) -> str:
    return json.dumps(fields) + "\n"


async def _save_upload(upload: UploadFile) -> tuple[str, int]:
    """
    Copies the upload to a temp file, enforcing MAX_AUDIO_BYTES while reading so
    an oversized (or endless) body is cut off instead of being read into memory.
    Returns (path, size_in_bytes). The caller owns deleting the file.
    """
    suffix = Path(upload.filename or "audio.webm").suffix.lower()
    if suffix not in _ALLOWED_AUDIO_SUFFIXES:
        suffix = ".webm"

    total = 0
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        while chunk := await upload.read(64 * 1024):
            total += len(chunk)
            if total > MAX_AUDIO_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"That recording is too large (limit {MAX_AUDIO_BYTES // (1024 * 1024)} MB).",
                )
            tmp.write(chunk)
    except BaseException:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise
    tmp.close()
    return tmp.name, total


async def _llm_tokens(messages: list, cancel: threading.Event):
    """
    Async generator over LLM tokens. The (blocking) Groq stream runs in its own
    thread and hands tokens over through an asyncio.Queue, so waiting for the
    next token never occupies a thread-pool worker (a per-token
    asyncio.to_thread(queue.get) would let a handful of slow streams starve the
    pool that STT and TTS share).
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    end = object()

    def put(item) -> None:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, item)
        except RuntimeError:
            pass  # loop already closed (server shutting down)

    def produce() -> None:
        try:
            for token in llm.chat_stream(messages, max_tokens=400):
                if cancel.is_set():
                    break
                put(token)
        except Exception as exc:  # delivered to the consumer, which reports it
            put(exc)
        finally:
            put(end)

    threading.Thread(target=produce, daemon=True, name="llm-stream").start()
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=LLM_TOKEN_TIMEOUT_SECONDS)
            except asyncio.TimeoutError as exc:
                raise TimeoutError("The language model stopped responding") from exc
            if item is end:
                return
            if isinstance(item, Exception):
                raise item
            yield str(item)
    finally:
        cancel.set()  # client went away / we're done: stop the producer between tokens


# ── Start / end a session ─────────────────────────────────────────────────────

@router.post("/start")
def start_conversation(
    background_tasks: BackgroundTasks,
    scenario: str = Form(default=DEFAULT_SCENARIO),
    style: str = Form(default=DEFAULT_STYLE),
    voice: str = Form(default=DEFAULT_VOICE),
    focus: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates a new conversation session for the authenticated user.

    The owner comes from the verified JWT — never from the request body, which
    previously let any caller claim any user_id (and auto-created that user).

    `focus` ("grammar:past_tense") optionally steers the conversation toward a
    weakness (see GET /api/practice/today); it must name a real subtype.

    The session's difficulty (the learner's pinned level, else the one their recent
    scores call for) is fixed here and kept for the whole session.

    The style brings an accent, so the companion must have a voice for it (see
    personalities.voice_for): a pair with none is refused with an explanation, and the
    model that holds the voice is loaded in the background so the first reply isn't slow.
    """
    if focus and taxonomy.parse_focus(focus) is None:
        raise HTTPException(status_code=400, detail=f"Unknown practice focus: {focus}")
    # Reject unknown ids up front; otherwise a bad voice only blows up later,
    # mid-conversation, as a TTS error.
    for value, allowed, what in (
        (scenario, SCENARIOS, "scenario"),
        (style, STYLES, "speaking style"),
        (voice, VOICES, "voice"),
    ):
        if value not in allowed:
            raise HTTPException(status_code=400, detail=f"Unknown {what}: {value}")
    if not tts.voice_available(voice):
        raise HTTPException(status_code=400, detail=f"The voice '{voice}' isn't installed on this server")
    problem = tts.style_problem(voice, style)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    level = difficulty.current(db, user)
    conversation = Conversation(
        user_id=user.id,
        scenario=scenario,
        style=style,
        voice=voice,
        focus=focus or None,
        difficulty=level["tier"],
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    background_tasks.add_task(tts.preload, voice, style)

    return {
        "conversation_id": conversation.id,
        "user_id": user.id,
        "scenario": scenario,
        "style": style,
        "voice": voice,
        "focus": conversation.focus,
        "difficulty": {"tier": level["tier"], "label": level["label"]},
    }


@router.post("/{conversation_id}/end")
def end_conversation(
    conversation_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Closes a session so history has a real duration and completion state, and
    starts building its report in the background (it first waits for the last
    turn's analysis to finish, so the final mistakes are in the score).
    Idempotent — ending an already-ended session returns the existing values.

    A session ended soon after its last message ends now. One that has been quiet for longer than
    IDLE_AFTER_LAST_MESSAGE (left open, then finished later from History) ends at its last message,
    so the idle gap is not counted as practice.
    """
    conversation = _owned_conversation(conversation_id, user, db)

    if not conversation.is_complete:
        now = datetime.now(timezone.utc)
        last_activity = (
            db.query(func.max(Message.created_at)).filter(Message.conversation_id == conversation.id).scalar()
        )
        last_activity = max(last_activity or conversation.started_at, conversation.started_at)
        conversation.ended_at = now if now - last_activity <= IDLE_AFTER_LAST_MESSAGE else last_activity
        conversation.is_complete = True
        db.commit()
        db.refresh(conversation)
        background_tasks.add_task(reports.generate_report_safely, conversation.id)

    return {
        "conversation_id": conversation.id,
        "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None,
        "is_complete": conversation.is_complete,
    }


# ── The voice loop ────────────────────────────────────────────────────────────

@router.post("/message-stream")
async def send_message_stream(
    conversation_id: str = Form(...),
    audio_file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    One spoken turn: audio in, then the transcript and the coach's reply (as
    sentence-sized audio chunks) streamed back as NDJSON — see the module
    docstring for the event types. The grammar/vocab analysis of the user's
    words starts as soon as the transcript is saved and runs concurrently with
    the spoken reply.
    """
    t_total = time.perf_counter()
    enforce("voice:user", user.id, VOICE_TURN_PER_USER, "You're sending turns too quickly. Take a breath and try again.")

    conversation = _owned_conversation(conversation_id, user, db)
    if conversation.is_complete:
        raise HTTPException(status_code=409, detail="This session has ended. Start a new session to keep practising.")

    # Plain values for the generator below: the ORM objects belong to a session
    # that we release right now. A turn takes several seconds; holding a pooled
    # connection through all of it would let ~15 simultaneous turns exhaust
    # the pool.
    user_id = user.id
    voice, style, scenario = conversation.voice, conversation.style, conversation.scenario
    level = conversation.difficulty      # None for sessions from before difficulty existed: no instruction
    focus_text = taxonomy.focus_for(*parsed) if (parsed := taxonomy.parse_focus(conversation.focus)) else None
    db.close()

    tmp_path, size = await _save_upload(audio_file)

    async def _stream():
        timings: dict = {}

        # ── STT ───────────────────────────────────────────────────────────────
        try:
            if size == 0:
                raise stt.AudioDecodeError("No audio was received. Please try again.")
            stt_result = await asyncio.to_thread(stt.transcribe, tmp_path)
        except (stt.AudioDecodeError, stt.STTUnavailableError) as exc:
            yield _event(type="error", message=str(exc))
            yield _event(type="done", full_reply="", timings=timings)
            return
        except Exception:
            logger.exception("Unexpected STT failure")
            yield _event(type="error", message="Speech recognition failed. Please try again.")
            yield _event(type="done", full_reply="", timings=timings)
            return
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        timings["stt_ms"] = stt_result["latency_ms"]
        transcript = stt_result["text"].strip()

        if not transcript:
            yield _event(type="error", message="No speech detected")
            yield _event(type="done", full_reply="", timings=timings)
            return
        if stt_result["duration"] > MAX_AUDIO_SECONDS:
            yield _event(type="error", message=f"That recording is too long (limit {MAX_AUDIO_SECONDS} seconds). Try a shorter answer.")
            yield _event(type="done", full_reply="", timings=timings)
            return

        # ── How they spoke (rate, pauses, fillers), saved with the turn ───────
        metrics = speech_metrics.analyse(stt_result)

        # ── Save the turn, then send the transcript immediately ───────────────
        message_id = await asyncio.to_thread(
            turns.persist_user_turn, conversation_id, user_id, transcript, stt_result, metrics
        )
        yield _event(type="transcript", text=transcript, message_id=message_id)
        yield _event(type="metrics", message_id=message_id, **speech_metrics.to_payload(metrics))

        # ── Grammar/vocab analysis starts now, in parallel with the reply ─────
        if turns.should_analyse(transcript):
            background.spawn(
                run_async_analysis,
                transcript=transcript,
                message_id=message_id,
                conversation_id=conversation_id,
                user_id=user_id,
                style=style,
            )

        # ── LLM streaming + sentence-chunked TTS ──────────────────────────────
        history = await asyncio.to_thread(turns.load_context, conversation_id)
        messages = llm.build_messages(
            build_system_prompt(scenario=scenario, style=style, difficulty=level, focus=focus_text), history
        )

        t_llm_start = time.perf_counter()
        timings["llm_ttfs_ms"] = None
        timings["first_audio_ms"] = None
        reply_parts: list[str] = []
        chunk_index = 0
        buffer = ""
        llm_failed = False

        async def speak(sentence: str) -> list[str]:
            """Synthesizes one sentence -> the events to emit (a chunk, or a warning)."""
            nonlocal chunk_index
            if timings["llm_ttfs_ms"] is None:
                timings["llm_ttfs_ms"] = round((time.perf_counter() - t_llm_start) * 1000, 1)
            reply_parts.append(sentence)
            t_tts = time.perf_counter()
            try:
                wav_bytes = await asyncio.to_thread(tts.synthesize_text, sentence, voice, style)
            except Exception:
                logger.exception("TTS failed for a sentence (voice=%s)", voice)
                return [_event(type="warning", message="Part of the reply couldn't be spoken, but the text is shown.")]
            if timings["first_audio_ms"] is None:
                timings["first_audio_ms"] = round((time.perf_counter() - t_total) * 1000, 1)
            event = _event(
                type="audio_chunk",
                index=chunk_index,
                text=sentence,
                data=base64.b64encode(wav_bytes).decode("utf-8"),
                tts_ms=round((time.perf_counter() - t_tts) * 1000, 1),
            )
            chunk_index += 1
            return [event]

        cancel = threading.Event()
        try:
            async for token in _llm_tokens(messages, cancel):
                buffer += token
                # The first chunk is the one the learner waits for in silence, so it
                # is allowed to be short; later chunks stay longer for better prosody.
                min_chars = tts.FIRST_CHUNK_MIN_CHARS if not reply_parts else tts.MIN_CHARS
                sentences, buffer = tts.split_sentences(buffer, min_chars=min_chars)
                for sentence in sentences:
                    for event in await speak(sentence):
                        yield event
            # Flush the tail (a reply that doesn't end in terminal punctuation)
            if len(buffer.strip()) >= 3:
                for event in await speak(buffer.strip()):
                    yield event
        except Exception as exc:
            llm_failed = True
            if llm.is_rate_limited(exc):
                logger.warning("The LLM provider is rate-limiting us; a turn got no reply")
                yield _event(type="error", message="The coach is very busy right now. Please try again in a few seconds.")
            else:
                logger.exception("LLM streaming failed")
                yield _event(type="error", message="The coach couldn't respond right now. Please try again.")

        # ── Save what was actually said, then finish ──────────────────────────
        full_reply = " ".join(reply_parts)
        if full_reply:
            await asyncio.to_thread(turns.persist_assistant_reply, conversation_id, full_reply)
        elif not llm_failed:
            yield _event(type="error", message="The coach didn't reply. Please try again.")

        timings["total_ms"] = round((time.perf_counter() - t_total) * 1000, 1)
        yield _event(type="done", full_reply=full_reply, timings=timings)

    async def generate():
        """
        Safety wrapper: catches any exception that escapes _stream() and
        emits a clean error + done so the HTTP chunked stream always terminates
        properly (avoids ChunkedEncodingError on the client).
        """
        try:
            async for chunk in _stream():
                yield chunk
        except Exception:
            logger.exception("Voice stream failed unexpectedly")
            yield _event(type="error", message="Something went wrong on our side. Please try again.")
            yield _event(type="done", full_reply="", timings={})

    # Safety net: _stream() deletes the upload itself, but if the client drops
    # before the first chunk is read the generator never runs.
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        background=BackgroundTask(lambda: Path(tmp_path).unlink(missing_ok=True)),
    )
