"""
Session reports (one per finished practice session) — the foundation that the
progress charts, weakness profile and adaptive difficulty are all computed from.

A report stores the scores AND the scoring version they were computed with
(services/scoring.py SCORING_VERSION), so when a formula changes you can tell
which old reports to recompute instead of silently mixing two meanings of
"grammar 82" on one chart.
"""
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base
from backend.models.core import utcnow


class SessionReport(Base):
    __tablename__ = "session_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    scoring_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # 0-100. NULL = no evidence for that dimension in this session (never a made-up 100).
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grammar_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vocabulary_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fluency_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clarity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    naturalness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # What the learner reads
    strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    improvements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    top_errors: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list,
        comment="[{category, subtype, label, count, example_original, example_correction}], most frequent first",
    )
    practice_words: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, comment="words the recogniser struggled with, most often first"
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="a short coach's note; NULL if it couldn't be written")

    # Session facts
    total_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    total_words: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    mistake_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    suggestion_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    praise_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_wpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    filler_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class UserWeakness(Base):
    """
    One row per kind of mistake a learner makes, recomputed from their corrections
    (services/weaknesses.py). It is a cache: dropping the table loses nothing,
    because every number here can be re-derived from `corrections`.
    """
    __tablename__ = "user_weaknesses"
    __table_args__ = (UniqueConstraint("user_id", "category", "subtype", name="uq_user_weakness"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    subtype: Mapped[str] = mapped_column(String(50), nullable=False)

    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, comment="all-time mistakes of this kind")
    recent_count: Mapped[int] = mapped_column(Integer, nullable=False, comment="in the last 30 days")
    previous_count: Mapped[int] = mapped_column(Integer, nullable=False, comment="in the 30 days before that")
    sessions_seen: Mapped[int] = mapped_column(Integer, nullable=False, comment="distinct sessions it appeared in")
    priority: Mapped[float] = mapped_column(Float, nullable=False, comment="ranking weight: recent mistakes count most")
    trend: Mapped[str] = mapped_column(String(12), nullable=False, comment="new | improving | stable | worsening")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
