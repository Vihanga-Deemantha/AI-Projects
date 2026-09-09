"""
AURA — AI English Speaking Coach
FastAPI application entry point.
"""
# pyrefly: ignore [missing-import]
from contextlib import asynccontextmanager
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

from backend.config import ENVIRONMENT
from backend.database import engine, Base
from backend.routers import health, conversation, analysis, config, auth, history


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs at startup and shutdown.
    Creates all DB tables on first run (idempotent — safe to run repeatedly).
    In production, use Alembic migrations instead.
    """
    import threading
    from backend.services import tts as _tts

    def _prewarm_tts():
        """
        Pre-loads all voice models on startup so the first user turn
        doesn't pay the .onnx load cost. Runs in a daemon thread.
        """
        try:
            for voice_id in ["amy", "ryan", "alan", "lessac"]:
                _tts._get_voice(voice_id)
        except Exception as e:
            print(f"[Startup] TTS pre-warm failed (non-fatal): {e}")

    threading.Thread(target=_prewarm_tts, daemon=True, name="tts-prewarm").start()

    Base.metadata.create_all(bind=engine)
    print("[Startup] Database tables verified / created")
    yield
    # (cleanup on shutdown goes here if needed)



app = FastAPI(
    title="AURA — AI English Speaking Coach",
    description="Real-time conversational English practice with personalized feedback.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Next.js dev server (localhost:3000) to call the API.
# Tighten this for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev server
        "http://localhost:5173",   # Vite dev server (if used)
    ] if ENVIRONMENT == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(conversation.router)
app.include_router(analysis.router)
app.include_router(config.router)
app.include_router(history.router)
