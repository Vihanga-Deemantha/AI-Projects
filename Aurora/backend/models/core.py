"""
Core SQLAlchemy ORM models.

Tables:
  users         — accounts (password and/or Google)
  conversations — a single practice session
  messages      — individual turns within a conversation
  corrections   — grammar / vocabulary / naturalness feedback on a user turn

Per-feature tables live beside this file: models/metrics.py (fluency, clarity)
and models/reports.py (session reports, weaknesses). models/__init__.py imports
them all so Alembic sees one complete schema.
"""
import uuid
from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, Integer, false, text
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
    # NULL hash simply can't log in — verify_password() rejects it. Also NULL
    # for Google-only accounts that have never set a password.
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="bcrypt hash; NULL for legacy anonymous users or Google-only accounts"
    )

    # Profile
    avatar_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Cloudinary CDN URL"
    )
    bio: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Google OAuth — NULL for accounts that have never linked Google
    google_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True,
        comment="Google subject ID; present on OAuth-created or linked accounts"
    )

    # Password reset OTP — all NULL/0 when no reset is pending
    reset_otp_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="bcrypt hash of the 6-digit OTP"
    )
    reset_otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reset_otp_attempts: Mapped[int] = mapped_column(
        Integer, default=0, comment="Failed OTP attempts this reset cycle; auto-expire after 3"
    )
    reset_otp_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When the last reset code was issued; enforces a resend cooldown"
    )

    # Email ownership. A password account is created with an unverified email,
    # so nothing may trust that address (e.g. auto-linking a Google login to it)
    # until the owner proves control of the inbox with the signup OTP, a
    # successful password reset, or by signing in with Google.
    email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(),
        comment="True once the owner has proven control of the email address"
    )
    verify_otp_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="bcrypt hash of the signup / verify-email OTP"
    )
    verify_otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verify_otp_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    verify_otp_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # A level the learner pinned for themselves; NULL = adapt automatically from
    # their recent scores (services/difficulty.py).
    difficulty_override: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="difficulty tier (1-5) the learner pinned; NULL = automatic"
    )

    # Bumped on password change/reset and on account takeover protection; every
    # JWT carries the value it was issued under, so bumping it logs out every
    # existing session at once.
    token_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
        comment="Embedded in JWTs; incrementing it revokes all existing tokens"
    )

    # User preferences — stored here so they persist across sessions
    preferred_voice: Mapped[str] = mapped_column(
        String(50), default="amy",
        comment="A key of personalities.VOICES (companion id)"
    )
    preferred_style: Mapped[str] = mapped_column(
        String(50), default="standard",
        comment="A key of personalities.STYLES"
    )

    # Relationships
    # passive_deletes: rely on the database's ON DELETE CASCADE instead of
    # loading every conversation/message into memory just to delete them
    # (deleting an account must stay cheap for a user with a long history).
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    # Plain @property, not a mapped column — from_attributes=True reads these
    # via getattr() same as any other field, so AuthUser.model_validate(user)
    # picks them up without the router ever touching password_hash/google_id.
    @property
    def has_password(self) -> bool:
        return self.password_hash is not None

    @property
    def google_linked(self) -> bool:
        return self.google_id is not None

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
        comment="A key of personalities.SCENARIOS"
    )
    style: Mapped[str] = mapped_column(
        String(50), default="standard",
        comment="Speaking style / English variety preset"
    )
    voice: Mapped[str] = mapped_column(
        String(50), default="amy",
        comment="Piper voice / companion id (personalities.VOICES)"
    )

    # The difficulty tier this session ran at, fixed when it started.
    difficulty: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="difficulty tier (1-5) this session ran at; NULL for sessions from before tiers existed"
    )

    # What this session was steering toward ("grammar:past_tense"), chosen from the
    # learner's weak spots (Phase 9). NULL = an ordinary open conversation.
    focus: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Computed when the session report is generated (services/reports.py)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Message.created_at",
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

    # Lifecycle of the async grammar/vocab analysis for a user turn:
    #   pending -> done | failed | skipped (too short to analyse).
    # Lets the API say "feedback is still coming" instead of "no feedback", and
    # lets session reports wait for in-flight analysis. Rows that predate the
    # column default to 'done'.
    analysis_status: Mapped[str] = mapped_column(
        String(10), default="done", server_default=text("'done'")
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

    # TRUE = praise: the learner used an idiom / phrasal verb / collocation well.
    # Never counted as a "correction" in totals; fuels strengths in the report.
    is_positive: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    
    # "high", "medium", "low"
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    
    # Relationships
    message: Mapped["Message"] = relationship()

