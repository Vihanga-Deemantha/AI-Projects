"""
Pydantic schemas for API request/response validation.
These are NOT database models — they define the API contract.
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal, Optional


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

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=100)
    bio: Optional[str] = Field(default=None, max_length=300)


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
    category: Literal["grammar", "vocabulary", "naturalness"]
    subtype: str
    original: str
    correction: str
    explanation: str
    is_error: bool = True
    severity: Literal["high", "medium", "low"] = "medium"


class AnalysisResult(BaseModel):
    corrections: list[CorrectionItem] = Field(default_factory=list)


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str        # "connected" | "error: ..."
    groq_api: str        # "connected" | "error: ..."
    llm_conversation_model: str
    llm_analysis_model: str
