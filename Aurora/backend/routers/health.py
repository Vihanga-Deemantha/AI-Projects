"""
Health check endpoint.

GET /health              — fast check, no outside calls: database, schema, speech models.
GET /health?full=true    — also pings the Groq API (adds ~2-5 s). Point an uptime monitor here.

It answers 503 (with the same JSON body) whenever the app can't do its job, so a
platform health check or uptime monitor can act on the status code alone.

The body is public, so failures name only the kind of error ("error: OperationalError"),
never its text: that can carry hostnames, ids and account details. The detail goes to the log.
"""
import logging

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Query, Response
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from sqlalchemy import text

from backend.database import engine, get_db
from backend.migrations_check import check_schema
from backend.services import llm, stt, tts
from backend.schemas.core import HealthResponse
from backend.config import ENVIRONMENT, LLM_CONVERSATION_MODEL, LLM_ANALYSIS_MODEL

logger = logging.getLogger("aura.health")

router = APIRouter(tags=["health"])


def _describe(exc: BaseException) -> str:
    return f"error: {type(exc).__name__}"


@router.get("/health", response_model=HealthResponse)
def health_check(
    response: Response,
    db: Session = Depends(get_db),
    full: bool = Query(default=False, description="Set to true to also ping Groq API"),
):
    """
    Fast check — database, schema version and speech models.
    Add ?full=true to also verify Groq API connectivity (adds ~2-5s).
    """
    # ── Database ──────────────────────────────────────────────────────────────
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Health check: the database is unreachable (%s)", exc)
        db_status = _describe(exc)

    # ── Schema: is the database at the revision this code expects? ────────────
    migrations = "unknown"
    if db_status == "connected":
        try:
            up_to_date, message = check_schema(engine)
            migrations = "up to date" if up_to_date else "behind"
            if not up_to_date:
                logger.warning("Health check: %s", message)
        except Exception as exc:
            logger.warning("Health check: couldn't read the schema version (%s)", exc)
            migrations = _describe(exc)

    # ── Speech models ─────────────────────────────────────────────────────────
    speech = {"stt": stt.status(), "voices": tts.status()}

    # ── Groq API (optional) ───────────────────────────────────────────────────
    groq_status = "skipped"
    if full:
        groq_status = "connected"
        try:
            llm.ping()
        except Exception as exc:
            if llm.is_rate_limited(exc):
                groq_status = "rate limited"      # reachable, just busy: not an outage
            else:
                logger.warning("Health check: the Groq API ping failed (%s)", exc)
                groq_status = _describe(exc)

    healthy = (
        db_status == "connected"
        and migrations == "up to date"
        and speech["voices"]["installed"] > 0     # with no voice installed the coach can't speak
        and not groq_status.startswith("error")
    )
    if not healthy:
        response.status_code = 503

    return HealthResponse(
        status="ok" if healthy else "degraded",
        environment=ENVIRONMENT,
        database=db_status,
        migrations=migrations,
        groq_api=groq_status,
        speech=speech,
        llm_conversation_model=LLM_CONVERSATION_MODEL,
        llm_analysis_model=LLM_ANALYSIS_MODEL,
    )
