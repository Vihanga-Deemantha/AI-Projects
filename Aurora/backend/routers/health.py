"""
Health check endpoint.
GET /health — verifies all subsystems are reachable.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db
from backend.services import llm
from backend.schemas.core import HealthResponse
from backend.config import ENVIRONMENT, LLM_CONVERSATION_MODEL, LLM_ANALYSIS_MODEL

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """
    Checks:
    1. Database connection (simple SELECT 1)
    2. Groq API connectivity (minimal chat call)
    """
    # ── Database check ────────────────────────────────────────────────────────
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    # ── Groq API check ────────────────────────────────────────────────────────
    groq_status = "connected"
    try:
        llm.ping()
    except Exception as e:
        groq_status = f"error: {e}"

    overall = "ok" if db_status == "connected" and groq_status == "connected" else "degraded"

    return HealthResponse(
        status=overall,
        environment=ENVIRONMENT,
        database=db_status,
        groq_api=groq_status,
        llm_conversation_model=LLM_CONVERSATION_MODEL,
        llm_analysis_model=LLM_ANALYSIS_MODEL,
    )
