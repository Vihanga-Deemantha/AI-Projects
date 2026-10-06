"""
Database operations for a single conversational turn.

Each function opens its own short-lived session. That keeps the streaming
endpoint independent of the request-scoped session (whose lifetime relative to
a streamed response has changed between FastAPI versions) and lets the async
generator run them with asyncio.to_thread so the event loop is never blocked
on the database.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import LLM_CONTEXT_MESSAGES
from backend.database import SessionLocal
from backend.models.core import Message
from backend.services import speech_metrics

logger = logging.getLogger("aura.turns")

# A turn still 'pending' after this long was almost certainly orphaned (the
# server restarted mid-analysis), so it must not keep clients — or session
# reports — waiting forever.
PENDING_STALE_AFTER = timedelta(minutes=2)

# Transcripts shorter than this aren't worth sending to the analysis model.
MIN_ANALYSIS_CHARS = 5


def load_context(conversation_id: str, limit: int = LLM_CONTEXT_MESSAGES) -> list[dict]:
    """
    The most recent `limit` messages, oldest first, as LLM chat messages.

    Newest-N, not oldest-N: ordering ascending and truncating (the original bug)
    freezes the context at the opening exchange, so after a few turns the coach
    never sees what the user just said.
    """
    with SessionLocal() as db:
        rows = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
            .all()
        )
    rows.reverse()
    return [{"role": m.role, "content": m.content} for m in rows]


def should_analyse(transcript: str) -> bool:
    return len(transcript.strip()) >= MIN_ANALYSIS_CHARS


def persist_user_turn(
    conversation_id: str,
    user_id: str,
    transcript: str,
    stt_result: dict,
    metrics: dict | None = None,
) -> str:
    """
    Saves the transcribed user turn with its raw STT metadata (word timings and
    confidence are kept so metrics can be recomputed later) and, in the same
    transaction, its speech metrics. Returns the new message id. The turn starts
    as analysis 'pending' unless it's too short to analyse.
    """
    with SessionLocal() as db:
        message = Message(
            conversation_id=conversation_id,
            role="user",
            content=transcript,
            audio_duration_seconds=stt_result["duration"],
            # Real JSON (not str(list)): downstream fluency code parses this.
            word_timestamps_json=json.dumps(stt_result["words"]),
            whisper_avg_logprob=stt_result["avg_logprob"],
            analysis_status="pending" if should_analyse(transcript) else "skipped",
        )
        db.add(message)
        db.flush()  # assigns message.id
        if metrics:
            # In a savepoint: if the metric rows can't be saved, the user's turn
            # itself must still go through.
            try:
                with db.begin_nested():
                    speech_metrics.save(db, message_id=message.id, user_id=user_id, conversation_id=conversation_id, metrics=metrics)
            except Exception:
                logger.exception("Could not save speech metrics for message %s", message.id)
        db.commit()
        return message.id


def persist_assistant_reply(conversation_id: str, text: str) -> str:
    with SessionLocal() as db:
        message = Message(conversation_id=conversation_id, role="assistant", content=text)
        db.add(message)
        db.commit()
        return message.id


def count_pending_analysis(db: Session, conversation_id: str) -> int:
    """How many of the user's turns in this conversation are still being analysed."""
    cutoff = datetime.now(timezone.utc) - PENDING_STALE_AFTER
    return (
        db.query(func.count(Message.id))
        .filter(
            Message.conversation_id == conversation_id,
            Message.role == "user",
            Message.analysis_status == "pending",
            Message.created_at > cutoff,
        )
        .scalar()
    ) or 0
