"""
Pydantic schemas for API request/response validation.
These are NOT database models — they define the API contract.
"""
from pydantic import BaseModel, EmailStr, Field, StrictInt, model_validator
from datetime import datetime
from typing import Literal, Optional

from backend.personalities import DIFFICULTY_LEVELS


# ── Users ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: Optional[str]
    display_name: Optional[str]
    preferred_voice: str
    preferred_style: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Auth ──────────────────────────────────────────────────────────────────────
# NOTE: UserResponse deliberately has no `password_hash` field. Because the
# auth routes are declared with response_model=..., FastAPI serialises through
# these schemas, so a hash cannot leak even if a full ORM object is returned.

class SignupRequest(BaseModel):
    email: EmailStr
    # 8 char floor; no max — services/auth.py pre-hashes, so bcrypt's 72-byte
    # limit doesn't apply and long passphrases stay fully significant.
    password: str = Field(min_length=8)
    display_name: Optional[str] = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthUser(BaseModel):
    id: str
    email: Optional[str]
    display_name: Optional[str]
    preferred_voice: str
    preferred_style: str
    created_at: datetime
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    # Computed on the User model (see models/core.py) — never read from
    # password_hash/google_id directly, so those two can never leak here.
    has_password: bool = True
    google_linked: bool = False
    email_verified: bool = False
    # A difficulty level the learner pinned (1-5); None = adapt automatically.
    difficulty_override: Optional[int] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=100)
    bio: Optional[str] = Field(default=None, max_length=300)
    # Validated against personalities.VOICES / STYLES in the router, so this
    # schema never hand-duplicates the list of valid ids.
    preferred_voice: Optional[str] = Field(default=None, max_length=50)
    preferred_style: Optional[str] = Field(default=None, max_length=50)
    # A tier of DIFFICULTY_LEVELS pins that level; an explicit null goes back to automatic.
    # (Whether the key was SENT matters, so the router checks `model_fields_set`.)
    # Strict, so `true` or "3" is refused instead of quietly becoming a level.
    difficulty_override: Optional[StrictInt] = Field(default=None, ge=min(DIFFICULTY_LEVELS), le=max(DIFFICULTY_LEVELS))


class VerifyEmailRequest(BaseModel):
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class DeleteAccountRequest(BaseModel):
    # The account's own email, typed back as a deliberate-action check.
    confirm_email: EmailStr
    # Required for accounts that have a password; Google-only accounts omit it.
    password: Optional[str] = None


class GoogleExchangeRequest(BaseModel):
    code: str = Field(min_length=10, max_length=2000)


class ChangePasswordRequest(BaseModel):
    # None only valid for a Google-only account setting a password for the
    # first time — the router enforces that distinction, not this schema.
    current_password: Optional[str] = None
    new_password: str = Field(min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8)


# ── Conversations ─────────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    user_id: str
    scenario: str = "casual"
    style: str = "standard"
    voice: str = "amy"


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    scenario: str
    style: str
    voice: str
    started_at: datetime
    is_complete: bool

    model_config = {"from_attributes": True}


# ── Messages ──────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Analysis (LLM output validation) ────────────────────────────────────────────
# Validates the JSON returned by the analysis LLM (services/analysis.py) before
# it is written to the corrections table — the model's output is untrusted input.

class CorrectionItem(BaseModel):
    """
    One piece of feedback on a spoken turn. Three kinds:
      mistake     is_error=True                    something wrong
      suggestion  is_error=False                   right, but could be better
      praise      is_positive=True (is_error=False) notably good use of English
    """
    category: Literal["grammar", "vocabulary", "naturalness"]
    subtype: str
    original: str = Field(min_length=1)
    correction: str = ""
    explanation: str = Field(min_length=1)
    is_error: bool = True
    is_positive: bool = False
    severity: Literal["high", "medium", "low"] = "medium"

    @model_validator(mode="after")
    def _consistent(self):
        if self.is_positive:
            # Praise is never an error, never "high" severity, and has no fix to
            # offer: its "correction" is simply the good wording itself.
            self.is_error = False
            self.severity = "low"
            if not self.correction.strip():
                self.correction = self.original
        elif not self.correction.strip():
            raise ValueError("a mistake or suggestion needs the better wording in `correction`")
        return self


class AnalysisResult(BaseModel):
    corrections: list[CorrectionItem] = Field(default_factory=list)


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str          # "ok" | "degraded" (the endpoint answers 503 when degraded)
    environment: str
    database: str        # "connected" | "error: <ErrorType>"
    migrations: str      # "up to date" | "behind" | "unknown" | "error: <ErrorType>"
    groq_api: str        # "skipped" | "connected" | "rate limited" | "error: <ErrorType>"
    speech: dict         # {"stt": {provider, ready}, "voices": {installed, total, loaded, missing}}
    llm_conversation_model: str
    llm_analysis_model: str
