"""
Speech history endpoints.

GET /api/history/sessions       — the user's past sessions (paginated)
GET /api/history/sessions/{id}  — one session: full transcript + corrections

Everything is scoped to the authenticated user; another user's session is
reported as 404 so ids can't be enumerated.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.core import Conversation, Correction, Message, User

router = APIRouter(prefix="/api/history", tags=["history"])


def _duration_seconds(conversation: Conversation) -> float | None:
    if not conversation.ended_at:
        return None
    return round((conversation.ended_at - conversation.started_at).total_seconds(), 1)


@router.get("/sessions")
def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Past sessions, newest first.

    Turn/correction counts come from two grouped aggregate queries rather than
    per-conversation counts inside the loop — that would be an N+1 that grows
    with history length.
    """
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.started_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    total = db.query(func.count(Conversation.id)).filter(
        Conversation.user_id == user.id
    ).scalar()

    ids = [c.id for c in conversations]
    turn_counts: dict[str, int] = {}
    correction_counts: dict[str, int] = {}

    if ids:
        # Only user turns count as "turns" — assistant replies aren't practice.
        turn_counts = dict(
            db.execute(
                select(Message.conversation_id, func.count(Message.id))
                .where(Message.conversation_id.in_(ids), Message.role == "user")
                .group_by(Message.conversation_id)
            ).all()
        )
        correction_counts = dict(
            db.execute(
                select(Correction.conversation_id, func.count(Correction.id))
                .where(Correction.conversation_id.in_(ids))
                .group_by(Correction.conversation_id)
            ).all()
        )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sessions": [
            {
                "id": c.id,
                "started_at": c.started_at.isoformat(),
                "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                "duration_seconds": _duration_seconds(c),
                "is_complete": c.is_complete,
                "scenario": c.scenario,
                "style": c.style,
                "voice": c.voice,
                "turn_count": turn_counts.get(c.id, 0),
                "correction_count": correction_counts.get(c.id, 0),
            }
            for c in conversations
        ],
    }


@router.get("/sessions/{conversation_id}")
def get_session(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """One session in full: ordered transcript plus corrections per user turn."""
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    corrections = (
        db.query(Correction)
        .filter(Correction.conversation_id == conversation_id)
        .order_by(Correction.created_at.asc())
        .all()
    )

    # Group corrections by the turn they belong to, so the UI can render them
    # inline against the right message instead of matching them client-side.
    by_message: dict[str, list] = {}
    for c in corrections:
        by_message.setdefault(c.message_id, []).append({
            "id": c.id,
            "category": c.category,
            "subtype": c.subtype,
            "original": c.original,
            "correction": c.correction,
            "explanation": c.explanation,
            "is_error": c.is_error,
            "severity": c.severity,
        })

    return {
        "id": conversation.id,
        "started_at": conversation.started_at.isoformat(),
        "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None,
        "duration_seconds": _duration_seconds(conversation),
        "is_complete": conversation.is_complete,
        "scenario": conversation.scenario,
        "style": conversation.style,
        "voice": conversation.voice,
        "turn_count": sum(1 for m in messages if m.role == "user"),
        "correction_count": len(corrections),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "audio_duration_seconds": m.audio_duration_seconds,
                "corrections": by_message.get(m.id, []),
            }
            for m in messages
        ],
    }
