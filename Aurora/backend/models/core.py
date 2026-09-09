"""
Core SQLAlchemy ORM models — Phase 0 schema.

Tables:
  users         — registered users (or anonymous sessions for now)
  conversations — a single practice session
  messages      — individual turns within a conversation
"""
import uuid
from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, Integer
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Nullable so pre-auth anonymous rows survive the migration. A row with a
    # NULL hash simply can't log in — verify_password() rejects it.
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="bcrypt hash; NULL for legacy anonymous users"
    )

    # User preferences — stored here so they persist across sessions
    preferred_voice: Mapped[str] = mapped_column(
        String(50), default="amy",
        comment="One of: amy, alan, ryan, lessac"
    )
    preferred_style: Mapped[str] = mapped_column(
        String(50), default="standard",
        comment="One of: standard, australian, irish, scouse, caribbean, pirate"
    )

    # Relationships
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r}>"


# ── Conversations ─────────────────────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Session configuration
    scenario: Mapped[str] = mapped_column(
        String(50), default="casual",
        comment="One of: casual, interview, travel, debate, professional, university"
    )
    style: Mapped[str] = mapped_column(
        String(50), default="standard",
        comment="Speaking style / English variety preset"
    )
    voice: Mapped[str] = mapped_column(
        String(50), default="amy",
        comment="Piper voice ID"
    )

    # Computed at end of session — will be populated in Phase 7
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id!r} scenario={self.scenario!r}>"


# ── Messages ──────────────────────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    role: Mapped[str] = mapped_column(
        String(10),
        comment="'user' or 'assistant'"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # STT metadata — stored raw so we can derive fluency metrics later without re-processing
    # These are only set on role='user' messages
    audio_duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    word_timestamps_json: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="JSON: [{word, start, end, probability}, ...] from faster-whisper"
    )
    whisper_avg_logprob: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="Average log-probability from Whisper — used as pronunciation proxy"
    )

    # Relationship
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id!r} role={self.role!r}>"


# ── Corrections ───────────────────────────────────────────────────────────────

class Correction(Base):
    __tablename__ = "corrections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    
    # "grammar", "vocabulary", or "naturalness"
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # E.g., "past_tense", "wrong_collocation"
    subtype: Mapped[str] = mapped_column(String(50), nullable=False)
    
    original: Mapped[str] = mapped_column(Text, nullable=False)
    correction: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    
    # TRUE = actual mistake (red label). FALSE = suggestion/improvement (blue label).
    is_error: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # "high", "medium", "low"
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    
    # Relationships
    message: Mapped["Message"] = relationship()

