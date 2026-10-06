"""
AURA — AI English Speaking Coach
FastAPI application entry point.
"""
import logging
import threading
from contextlib import asynccontextmanager

# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

from backend.config import (
    CHECK_MIGRATIONS_ON_STARTUP,
    CORS_ORIGINS,
    ENVIRONMENT,
    IS_DEVELOPMENT,
    MAX_AUDIO_BYTES,
    PREWARM_MODELS,
    SENTRY_DSN,
)
from backend.database import engine
from backend.logging_config import configure_logging
from backend.middleware import BodySizeLimitMiddleware
from backend.observability import init_error_tracking
from backend.routers import health, conversation, analysis, config, auth, google, history, practice, progress, speech

configure_logging()
logger = logging.getLogger("aura.main")

init_error_tracking(SENTRY_DSN, ENVIRONMENT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs at startup and shutdown.

    Schema management belongs to Alembic, not create_all(): startup only
    CHECKS that the database is at the expected revision. In development a
    mismatch is a loud error (the app may still limp along); in any other
    environment it stops the process, so a bad deploy fails immediately instead
    of 500-ing on real requests.
    """
    if CHECK_MIGRATIONS_ON_STARTUP:
        from backend.migrations_check import check_schema

        up_to_date, message = check_schema(engine)
        if up_to_date:
            logger.info(message)
        elif IS_DEVELOPMENT:
            logger.error(message)
        else:
            raise RuntimeError(message)

    if not IS_DEVELOPMENT:
        from backend import production_checks

        production_checks.run()      # logs the checklist's findings; never blocks startup

    if PREWARM_MODELS:
        from backend.services import stt, tts

        def _prewarm() -> None:
            # Whisper first: it loads lazily and that load (~3 s) happens before
            # the STT timer starts, so without this the very first user turn
            # silently pays for it. Then the six ~60-120 MB voice models.
            stt.prewarm()
            tts.prewarm()

        # Off the startup path so the server can answer /health right away.
        threading.Thread(target=_prewarm, daemon=True, name="model-prewarm").start()

    yield
    # (cleanup on shutdown goes here if needed)


app = FastAPI(
    title="AURA — AI English Speaking Coach",
    description="Real-time conversational English practice with personalized feedback.",
    version="0.2.0",
    lifespan=lifespan,
)

# ── Request size limits ───────────────────────────────────────────────────────
# Audio turns and avatars legitimately carry files; everything else is small JSON.
app.add_middleware(
    BodySizeLimitMiddleware,
    limits=[
        ("/api/conversation/message-stream", MAX_AUDIO_BYTES + 256 * 1024),
        ("/api/auth/avatar", 5 * 1024 * 1024 + 256 * 1024),
    ],
    default=1_000_000,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Origins come from config (CORS_ORIGINS / FRONTEND_URL); see backend/config.py.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(google.router)
app.include_router(conversation.router)
app.include_router(analysis.router)
app.include_router(config.router)
app.include_router(history.router)
app.include_router(practice.router)
app.include_router(progress.router)
app.include_router(speech.router)
