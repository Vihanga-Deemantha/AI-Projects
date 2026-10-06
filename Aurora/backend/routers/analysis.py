"""
Analysis endpoints.

GET /api/analysis/conversation/{id}/recent — the latest corrections for a
conversation, plus how many turns are still being analysed.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend import taxonomy
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.core import Conversation, Correction, User
from backend.services.turns import count_pending_analysis

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

def correction_to_dict(c: Correction) -> dict:
    return {
        "id": c.id,
        "message_id": c.message_id,
        "category": c.category,
        "subtype": c.subtype,
        "label": taxonomy.label_for(c.category, c.subtype),
        "original": c.original,
        "correction": c.correction,
        "explanation": c.explanation,
        "is_error": c.is_error,
        "is_positive": c.is_positive,
        "severity": c.severity,
        "created_at": c.created_at.isoformat(),
    }


@router.get("/conversation/{conversation_id}/recent")
def get_recent_corrections(
    conversation_id: str,
    limit: int = Query(default=5, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Fetches the most recent corrections for a given conversation.
    Used by the client to poll for async grammar/vocab feedback: `pending` is
    the number of user turns whose analysis hasn't finished yet, so the client
    knows whether to keep polling.
    """
    # Ownership check: filtering on user_id too means another user's
    # conversation is indistinguishable from a nonexistent one.
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    corrections = (
        db.query(Correction)
        .filter_by(conversation_id=conversation_id)
        .order_by(Correction.created_at.desc())
        .limit(limit)
        .all()
    )

    # We return them in chronological order so they display naturally
    return {
        "corrections": [correction_to_dict(c) for c in reversed(corrections)],
        "pending": count_pending_analysis(db, conversation_id),
    }
