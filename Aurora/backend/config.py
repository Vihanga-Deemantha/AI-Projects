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
