"""
Pydantic schemas for API request/response validation.
These are NOT database models — they define the API contract.
"""
from pydantic import BaseModel, Field
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
