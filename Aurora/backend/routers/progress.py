"""
Progress endpoint.

GET /api/progress/summary — weekly score trends, practice streak, totals and
milestones, computed from the learner's session reports (services/progress.py).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.core import Conversation, User
from backend.models.reports import SessionReport
from backend.services import progress, reports

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("/summary")
def progress_summary(
    weeks: int = Query(default=12, ge=4, le=52, description="How many weeks of trend to return"),
    tz_offset: int = Query(default=0, ge=-840, le=840, description="The learner's offset from UTC in minutes (e.g. 330 for India), so days and weeks are theirs"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Sessions from before reports existed get one now (no LLM note), so a
    # long-time learner's chart isn't empty on first visit.
    reports.backfill_missing(user.id)

    rows = db.execute(
        select(SessionReport, Conversation)
        .join(Conversation, Conversation.id == SessionReport.conversation_id)
        .where(SessionReport.user_id == user.id, Conversation.is_complete.is_(True))
        .order_by(Conversation.ended_at)
    ).all()

    points = [
        progress.Point(
            conversation_id=conversation.id,
            when=conversation.ended_at or conversation.started_at,
            scores={
                "overall": report.overall_score, "grammar": report.grammar_score, "vocabulary": report.vocabulary_score,
                "fluency": report.fluency_score, "clarity": report.clarity_score, "naturalness": report.naturalness_score,
            },
            duration_seconds=report.duration_seconds or 0.0,
            turns=report.total_turns,
            words=report.total_words,
            praise=report.praise_count,
        )
        for report, conversation in rows
    ]
    return progress.summarize(points, datetime.now(timezone.utc), tz_offset_minutes=tz_offset, weeks=weeks)
