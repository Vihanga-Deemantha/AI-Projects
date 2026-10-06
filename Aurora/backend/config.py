"""
Central configuration. All environment variables are loaded here.
Other modules import from this file — never call os.environ directly elsewhere.
"""
# pyrefly: ignore [missing-import]
import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: bool) -> bool:
    """Reads a boolean env var: 1/true/yes/on (case-insensitive) are True."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str) -> list[str]:
    """Reads a comma-separated env var into a list of non-empty, trimmed items."""
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


# ── Groq ────────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.environ["GROQ_API_KEY"]  # Hard fail if missing

# Two separate models: quality for conversation, speed for analysis
LLM_CONVERSATION_MODEL: str = os.getenv("LLM_CONVERSATION_MODEL", "openai/gpt-oss-120b")
# Analysis quality matters more than speed here (it runs in the background while the
# coach is speaking). In the regression suite (tests/regression), gpt-oss-120b passed all
# 23 cases it was tuned on and gpt-oss-20b 20 of 23 (once flagging correct English as a
# mistake, the worst failure for a learner). Model output varies a little from run to run,
# so re-run the suite before concluding anything from a single failure.
LLM_ANALYSIS_MODEL: str = os.getenv("LLM_ANALYSIS_MODEL", "openai/gpt-oss-120b")

# The gpt-oss models are REASONING models: they emit internal reasoning tokens
# that count against max_tokens before any user-facing content appears. At the
# default effort that reasoning is long and highly variable (~600-1100 chars),
# which intermittently exhausted the budget and produced truncated — or
# completely empty — replies, and inflated time-to-first-audio. "low" keeps it
# short and predictable (~120 chars).
# Set to an empty string if you switch to a non-reasoning model (llama-*),
# which does not accept this parameter.
LLM_REASONING_EFFORT: str = os.getenv("LLM_REASONING_EFFORT", "low")

# How many of the most recent messages the conversation LLM sees each turn.
LLM_CONTEXT_MESSAGES: int = int(os.getenv("LLM_CONTEXT_MESSAGES", "20"))

# A live reply fails fast when the provider is rate-limiting us (the learner is waiting),
# but the analysis runs in the background and can afford to wait it out: this many retries,
# each honouring the provider's Retry-After, before it gives up.
LLM_ANALYSIS_RETRIES: int = max(0, int(os.getenv("LLM_ANALYSIS_RETRIES", "5")))

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

# bcrypt work factor for passwords and one-time codes. 12 is the production
# default (~250 ms per hash); the test suite lowers it so hundreds of
# signups/logins don't take minutes. Verifying any existing hash works at any value.
BCRYPT_ROUNDS: int = max(4, min(15, int(os.getenv("BCRYPT_ROUNDS", "12"))))

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

# ── App ───────────────────────────────────────────────────────────────────────
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
IS_DEVELOPMENT: bool = ENVIRONMENT == "development"

# Logs every SQL statement — very noisy and it puts emails/transcripts in the
# logs, so it is opt-in even in development.
SQL_ECHO: bool = _flag("SQL_ECHO", False)

# Where the frontend lives — used to build the redirect URL after Google OAuth
# completes (the backend can't render the SPA itself, so it bounces the
# browser back to it).
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

# Browser origins allowed to call the API. Comma-separated. FRONTEND_URL is
# always allowed; in development the usual localhost dev servers are added too.
_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ORIGINS: list[str] = list(dict.fromkeys(
    [o.rstrip("/") for o in _csv("CORS_ORIGINS")]
    + ([FRONTEND_URL] if FRONTEND_URL else [])
    + (_DEV_ORIGINS if IS_DEVELOPMENT else [])
))

# The OAuth state cookie is only sent over HTTPS when the callback is HTTPS
# (i.e. outside local development).
COOKIE_SECURE: bool = GOOGLE_REDIRECT_URI.startswith("https://")

# Startup behaviour
PREWARM_MODELS: bool = _flag("PREWARM_MODELS", True)              # load Whisper + every voice at boot
CHECK_MIGRATIONS_ON_STARTUP: bool = _flag("CHECK_MIGRATIONS_ON_STARTUP", True)

# Optional error tracking (Sentry); ignored when unset. See backend/observability.py.
SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")

# ── Speech-to-text ───────────────────────────────────────────────────────────
# "local" runs faster-whisper on this machine's CPU (private, offline, but it
# slows down sharply with several simultaneous users). "groq" sends the audio
# to Groq's hosted Whisper — faster under load, much more accurate on accented
# speech, and it keeps filler words ("um", "uh") that local base.en drops.
STT_PROVIDER: str = os.getenv("STT_PROVIDER", "local").strip().lower()
GROQ_STT_MODEL: str = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")

WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "base.en")
WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# ── Audio ────────────────────────────────────────────────────────────────────
SAMPLE_RATE: int = 16_000

# Upload limits for a single spoken turn. 5 MB is ~2.5 min of 16 kHz WAV and
# far more than a minute of browser webm/opus; the duration cap is checked
# after transcription. The web UI auto-stops recording at 60 s.
MAX_AUDIO_BYTES: int = int(os.getenv("MAX_AUDIO_BYTES", str(5 * 1024 * 1024)))
MAX_AUDIO_SECONDS: int = int(os.getenv("MAX_AUDIO_SECONDS", "120"))

# ── Rate limiting ────────────────────────────────────────────────────────────
# In-memory and per-process: correct for the single-worker deployment this app
# targets (one Whisper/Piper copy in RAM). Move it to Redis if you ever run
# several workers.
RATE_LIMITS_ENABLED: bool = _flag("RATE_LIMITS_ENABLED", True)

# ── Voices ───────────────────────────────────────────────────────────────────
# Path is relative to the project root (Aurora/), not the backend/ folder.
# Resolved at runtime in tts.py using pathlib.
VOICES_DIR: str = os.getenv("VOICES_DIR", "voices")
