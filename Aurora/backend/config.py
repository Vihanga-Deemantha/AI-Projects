"""
Central configuration. All environment variables are loaded here.
Other modules import from this file — never call os.environ directly elsewhere.
"""
# pyrefly: ignore [missing-import]
import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

# ── Groq ────────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.environ["GROQ_API_KEY"]  # Hard fail if missing

# Two separate models: quality for conversation, speed for analysis
LLM_CONVERSATION_MODEL: str = os.getenv("LLM_CONVERSATION_MODEL", "openai/gpt-oss-120b")
LLM_ANALYSIS_MODEL: str = os.getenv("LLM_ANALYSIS_MODEL", "openai/gpt-oss-20b")

# The gpt-oss models are REASONING models: they emit internal reasoning tokens
# that count against max_tokens before any user-facing content appears. At the
# default effort that reasoning is long and highly variable (~600-1100 chars),
# which intermittently exhausted the budget and produced truncated — or
# completely empty — replies, and inflated time-to-first-audio. "low" keeps it
# short and predictable (~120 chars).
# Set to an empty string if you switch to a non-reasoning model (llama-*),
# which does not accept this parameter.
LLM_REASONING_EFFORT: str = os.getenv("LLM_REASONING_EFFORT", "low")

# ── Database ─────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.environ["DATABASE_URL"]  # Hard fail if missing

# ── Auth (JWT) ───────────────────────────────────────────────────────────────
# Hard fail if missing: a default/fallback secret would silently make every
# issued token forgeable. Generate one with:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
# Rotating this invalidates all existing sessions (everyone gets logged out).
JWT_SECRET: str = os.environ["JWT_SECRET"]
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

# ── Google OAuth (Phase 3c) ─────────────────────────────────────────────────
# Soft-optional, unlike JWT_SECRET/GROQ_API_KEY above: leaving these unset
# must not crash the whole backend (practice/history are unrelated to Google
# sign-in) — routers/google.py checks for a non-empty value itself and 503s
# with a clear message the first time a Google endpoint is actually hit.
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")

# ── Email / OTP — Resend (Phase 3c) ─────────────────────────────────────────
RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@aura.app")

# ── Avatar storage — Cloudinary (Phase 3c) ──────────────────────────────────
CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")

# Where the frontend lives — used to build the redirect URL after Google OAuth
# completes (the backend can't render the SPA itself, so it bounces the
# browser back with the token in the query string).
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

# ── Whisper ──────────────────────────────────────────────────────────────────
WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "base.en")
WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# ── App ───────────────────────────────────────────────────────────────────────
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Audio ────────────────────────────────────────────────────────────────────
SAMPLE_RATE: int = 16_000

# ── Voices ───────────────────────────────────────────────────────────────────
# Path is relative to the project root (Aurora/), not the backend/ folder.
# Resolved at runtime in tts.py using pathlib.
VOICES_DIR: str = os.getenv("VOICES_DIR", "voices")
