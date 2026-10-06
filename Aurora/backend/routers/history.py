"""
Speech history endpoints.

GET /api/history/sessions       — the user's past sessions (paginated)
GET /api/history/sessions/{id}  — one session: full transcript + corrections

Everything is scoped to the authenticated user; another user's session is
reported as 404 so ids can't be enumerated.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend import taxonomy
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.core import Conversation, Correction, Message, User
from backend.models.metrics import ClarityScore, FluencyScore
from backend.personalities import DIFFICULTY_LEVELS
from backend.services import reports, speech_metrics
from backend.services.turns import count_pending_analysis

router = APIRouter(prefix="/api/history", tags=["history"])

# A session that ended this recently, with analysis still running, is "still being
# written up" (202) rather than reported on with half its feedback missing.
REPORT_PENDING_WINDOW = timedelta(seconds=40)


def _duration_seconds(conversation: Conversation) -> float | None:
    if not conversation.ended_at:
        return None
    return round((conversation.ended_at - conversation.started_at).total_seconds(), 1)


def _difficulty(conversation: Conversation) -> dict | None:
    """The level a session ran at, or None for one from before levels existed."""
    level = DIFFICULTY_LEVELS.get(conversation.difficulty)
    return {"tier": conversation.difficulty, "label": level["label"]} if level else None


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
    praise_counts: dict[str, int] = {}
    avg_fluency: dict[str, int] = {}
    avg_clarity: dict[str, int] = {}

    if ids:
        # Only user turns count as "turns" — assistant replies aren't practice.
        turn_counts = dict(
            (cid, n) for cid, n in db.execute(
                select(Message.conversation_id, func.count(Message.id))
                .where(Message.conversation_id.in_(ids), Message.role == "user")
                .group_by(Message.conversation_id)
            ).all()
        )
        # Praise ("nice idiom!") isn't a correction, so it is counted separately.
        correction_counts = dict(
            (cid, n) for cid, n in db.execute(
                select(Correction.conversation_id, func.count(Correction.id))
                .where(Correction.conversation_id.in_(ids), Correction.is_positive.is_(False))
                .group_by(Correction.conversation_id)
            ).all()
        )
        praise_counts = dict(
            (cid, n) for cid, n in db.execute(
                select(Correction.conversation_id, func.count(Correction.id))
                .where(Correction.conversation_id.in_(ids), Correction.is_positive.is_(True))
                .group_by(Correction.conversation_id)
            ).all()
        )
        avg_fluency = {
            cid: round(avg)
            for cid, avg in db.execute(
                select(FluencyScore.conversation_id, func.avg(FluencyScore.score))
                .where(FluencyScore.conversation_id.in_(ids))
                .group_by(FluencyScore.conversation_id)
            ).all()
        }
        avg_clarity = {
            cid: round(avg)
            for cid, avg in db.execute(
                select(ClarityScore.conversation_id, func.avg(ClarityScore.score))
                .where(ClarityScore.conversation_id.in_(ids))
                .group_by(ClarityScore.conversation_id)
            ).all()
        }

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
                "overall_score": c.overall_score,
                "scenario": c.scenario,
                "style": c.style,
                "voice": c.voice,
                "difficulty": _difficulty(c),
                "turn_count": turn_counts.get(c.id, 0),
                "correction_count": correction_counts.get(c.id, 0),
                "praise_count": praise_counts.get(c.id, 0),
                "avg_fluency": avg_fluency.get(c.id),
                "avg_clarity": avg_clarity.get(c.id),
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

    fluency_rows = (
        db.query(FluencyScore)
        .options(selectinload(FluencyScore.events))   # one extra query, not one per turn
        .filter(FluencyScore.conversation_id == conversation_id)
        .all()
    )
    fluency_by_message = {f.message_id: speech_metrics.fluency_row_to_dict(f) for f in fluency_rows}
    clarity_rows = db.query(ClarityScore).filter(ClarityScore.conversation_id == conversation_id).all()
    clarity_by_message = {c.message_id: speech_metrics.clarity_row_to_dict(c) for c in clarity_rows}

    # Group corrections by the turn they belong to, so the UI can render them
    # inline against the right message instead of matching them client-side.
    by_message: dict[str, list] = {}
    for c in corrections:
        by_message.setdefault(c.message_id, []).append({
            "id": c.id,
            "category": c.category,
            "subtype": c.subtype,
            "label": taxonomy.label_for(c.category, c.subtype),
            "original": c.original,
            "correction": c.correction,
            "explanation": c.explanation,
            "is_error": c.is_error,
            "is_positive": c.is_positive,
            "severity": c.severity,
        })

    return {
        "id": conversation.id,
        "started_at": conversation.started_at.isoformat(),
        "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None,
        "duration_seconds": _duration_seconds(conversation),
        "is_complete": conversation.is_complete,
        "overall_score": conversation.overall_score,
        "scenario": conversation.scenario,
        "style": conversation.style,
        "voice": conversation.voice,
        "difficulty": _difficulty(conversation),
        "turn_count": sum(1 for m in messages if m.role == "user"),
        "correction_count": sum(1 for c in corrections if not c.is_positive),
        "praise_count": sum(1 for c in corrections if c.is_positive),
        "avg_fluency": round(sum(f.score for f in fluency_rows) / len(fluency_rows)) if fluency_rows else None,
        "avg_clarity": round(sum(c.score for c in clarity_rows) / len(clarity_rows)) if clarity_rows else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "audio_duration_seconds": m.audio_duration_seconds,
                "corrections": by_message.get(m.id, []),
                "fluency": fluency_by_message.get(m.id),
                "clarity": clarity_by_message.get(m.id),
            }
            for m in messages
        ],
    }


@router.get("/sessions/{conversation_id}/report")
def get_session_report(
    conversation_id: str,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    The report for a finished session.

      200 {"status": "ready", "report": {...}}
      202 {"status": "pending"}   — it ended seconds ago and the last turn is still being
                                    analysed; ask again in a moment
      404                         — nothing was said, so there is nothing to report on
      409                         — the session hasn't ended yet

    Sessions that ended before reports existed (or whose background task missed) are
    reported on the first time they are opened.
    """
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Session not found")
    if not conversation.is_complete:
        raise HTTPException(status_code=409, detail="End the session to see its report.")

    existing = reports.get_report(db, conversation_id)
    if existing:
        return {"status": "ready", "report": reports.report_to_dict(existing)}

    just_ended = (
        conversation.ended_at is not None
        and datetime.now(timezone.utc) - conversation.ended_at < REPORT_PENDING_WINDOW
    )
    if just_ended and count_pending_analysis(db, conversation_id) > 0:
        response.status_code = 202
        return {"status": "pending"}

    generated = reports.generate_report(conversation_id)
    if generated is None:
        raise HTTPException(status_code=404, detail="This session has no turns to report on.")
    return {"status": "ready", "report": generated}
