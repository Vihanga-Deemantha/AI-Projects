"""
Per-turn speech metrics: computed once when a turn is spoken, stored so session
reports and progress charts can aggregate them without re-processing audio.

  fluency_scores   one row per user turn — rate, pauses, fillers, repetitions
  fluency_events   one row per individual pause / filler / repetition, with its
                   timestamp (so you can ask "which filler do I overuse?" across
                   every session, or highlight them inline in a transcript)
  clarity_scores   one row per user turn — speech-recognition confidence (an estimate,
                   not phoneme-level pronunciation analysis; see services/clarity.py)
"""
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.core import utcnow


class FluencyScore(Base):
    __tablename__ = "fluency_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Denormalised owner + session so reports and progress queries need no joins.
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="0-100; see services/fluency.compute_score")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    speech_seconds: Mapped[float] = mapped_column(Float, nullable=False, comment="first word start -> last word end")
    wpm: Mapped[float | None] = mapped_column(Float, nullable=True, comment="NULL when there was too little speech to say")
    articulation_wpm: Mapped[float | None] = mapped_column(Float, nullable=True, comment="speaking rate with pauses removed")
    pause_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    long_pause_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_pause_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    longest_pause_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    filler_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filler_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment='e.g. {"um": 3, "you know": 1}')
    repetition_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hesitations_tracked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="False when the recogniser drops um/uh, so a filler count of 0 means 'couldn't hear them'"
    )

    events: Mapped[list["FluencyEvent"]] = relationship(
        back_populates="fluency", cascade="all, delete-orphan", passive_deletes=True,
        order_by="FluencyEvent.start_seconds",
    )


class FluencyEvent(Base):
    __tablename__ = "fluency_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    fluency_score_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fluency_scores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    kind: Mapped[str] = mapped_column(String(12), nullable=False, comment="pause | long_pause | filler | repetition")
    text: Mapped[str] = mapped_column(String(100), nullable=False, comment="the filler/repeated word, or the pause length")
    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    fluency: Mapped["FluencyScore"] = relationship(back_populates="events")


class ClarityScore(Base):
    __tablename__ = "clarity_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="0-100 estimate from speech-recognition confidence")
    word_level: Mapped[bool] = mapped_column(
        Boolean, nullable=False, comment="False = rough estimate from segment confidence only (no per-word confidences)"
    )
    avg_word_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_logprob: Mapped[float] = mapped_column(Float, nullable=False)
    words_scored: Mapped[int] = mapped_column(Integer, nullable=False)
    unclear_words: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, comment="[{word, probability, start, end}] — the least clearly recognised words"
    )
