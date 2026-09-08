"""
Health check endpoint.
GET /health — fast liveness check (DB only).
GET /health?full=true — full check including Groq API ping.
"""
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Query
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from sqlalchemy import text

from backend.database import get_db
# pyrefly: ignore [missing-import]
from backend.services import llm
from backend.schemas.core import HealthResponse
from backend.config import ENVIRONMENT, LLM_CONVERSATION_MODEL, LLM_ANALYSIS_MODEL

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Session = Depends(get_db),
    full: bool = Query(default=False, description="Set to true to also ping Groq API"),
):
    """
    Fast liveness check — always checks DB.
    Add ?full=true to also verify Groq API connectivity (adds ~2-5s).
    """
    # ── Database check ────────────────────────────────────────────────────────
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    # ── Groq API check (optional) ─────────────────────────────────────────────
    groq_status = "skipped"
    if full:
        groq_status = "connected"
        try:
            llm.ping()
        except Exception as e:
            groq_status = f"error: {e}"

    overall = "ok" if db_status == "connected" else "degraded"

    return HealthResponse(
        status=overall,
        environment=ENVIRONMENT,
        database=db_status,
        groq_api=groq_status,
        llm_conversation_model=LLM_CONVERSATION_MODEL,
        llm_analysis_model=LLM_ANALYSIS_MODEL,
    )
