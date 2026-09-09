from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.core import Conversation, Correction, User

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

@router.get("/conversation/{conversation_id}/recent")
def get_recent_corrections(
    conversation_id: str,
    limit: int = Query(default=5, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Fetches the most recent corrections for a given conversation.
    Used by the client to poll for async grammar/vocab feedback.
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
        "corrections": [
            {
                "id": c.id,
                "message_id": c.message_id,
                "category": c.category,
                "subtype": c.subtype,
                "original": c.original,
                "correction": c.correction,
                "explanation": c.explanation,
                "is_error": c.is_error,
                "severity": c.severity,
                "created_at": c.created_at.isoformat(),
            }
            for c in reversed(corrections)
        ]
    }
