"""
AURA setup check — run from the Aurora/ folder with the venv active:

    python check_setup.py                # server setup
    python check_setup.py --local-client # also check the microphone for local_client.py

Verifies the things that most often go wrong on a fresh machine: packages, the
.env file, the database and its migrations, the six voice models plus the two
accent models behind the speaking styles, and (if you choose it) Groq connectivity. It makes one tiny Groq request, so it uses a
little quota.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

parser = argparse.ArgumentParser()
parser.add_argument("--local-client", action="store_true", help="also check the microphone/VAD packages used by local_client.py")
parser.add_argument("--skip-groq", action="store_true", help="don't make the live Groq request")
args = parser.parse_args()

problems: list[str] = []
warnings: list[str] = []


def ok(message: str) -> None:
    print(f"  OK    {message}")


def warn(message: str) -> None:
    warnings.append(message)
    print(f"  WARN  {message}")


def fail(message: str) -> None:
    problems.append(message)
    print(f"  FAIL  {message}")


print(f"Python {sys.version.split()[0]}  ({sys.executable})\n")

# ── 1. Virtual environment ────────────────────────────────────────────────────
if sys.prefix == sys.base_prefix:
    fail("Not running inside the virtual environment — activate it first (venv\\Scripts\\activate).")
else:
    ok("running inside a virtual environment")

# ── 2. Packages ───────────────────────────────────────────────────────────────
required = {
    "fastapi": "fastapi", "uvicorn": "uvicorn[standard]", "sqlalchemy": "sqlalchemy", "alembic": "alembic",
    "psycopg2": "psycopg2-binary", "faster_whisper": "faster-whisper", "piper": "piper-tts", "numpy": "numpy",
    "dotenv": "python-dotenv", "groq": "groq", "pydantic": "pydantic", "bcrypt": "bcrypt", "jose": "python-jose",
    "httpx": "httpx", "multipart": "python-multipart", "email_validator": "email-validator",
    "resend": "resend", "cloudinary": "cloudinary",
}
if args.local_client:
    required.update({"sounddevice": "sounddevice", "torch": "torch", "silero_vad": "silero-vad", "requests": "requests"})
for module, package in required.items():
    try:
        __import__(module)
    except ImportError:
        fail(f"Missing package '{module}' — pip install {package}   (or: pip install -r backend/requirements.txt)")
print(f"  checked {len(required)} packages")

# ── 3. .env ───────────────────────────────────────────────────────────────────
from dotenv import load_dotenv  # noqa: E402

env_path = ROOT / ".env"
if not env_path.exists():
    fail(".env not found — copy .env.example to .env and fill it in")
load_dotenv(env_path)

for key in ("GROQ_API_KEY", "DATABASE_URL", "JWT_SECRET"):
    if not os.environ.get(key):
        fail(f"{key} is not set in .env")
    else:
        ok(f"{key} is set")
if os.environ.get("JWT_SECRET", "").startswith("replace_me"):
    fail("JWT_SECRET is still the placeholder — generate one: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")

optional = {
    "GOOGLE_CLIENT_ID": "Google sign-in", "RESEND_API_KEY": "emailed codes (password reset, email verification)",
    "CLOUDINARY_CLOUD_NAME": "profile photos",
}
for key, feature in optional.items():
    if not os.environ.get(key):
        warn(f"{key} is empty — {feature} is disabled")
provider = os.environ.get("STT_PROVIDER", "local")
ok(f"speech-to-text provider: {provider}" + ("  (local Whisper; set STT_PROVIDER=groq for better accuracy + filler words)" if provider == "local" else ""))
if os.environ.get("SENTRY_DSN"):
    try:
        import sentry_sdk  # noqa: F401
        ok("error tracking: Sentry is configured")
    except ImportError:
        warn("SENTRY_DSN is set but sentry-sdk isn't installed — pip install -r backend/requirements.txt")

# ── 4. Database + migrations ─────────────────────────────────────────────────
db_url = os.environ.get("DATABASE_URL")
if db_url and os.environ.get("JWT_SECRET") and os.environ.get("GROQ_API_KEY"):
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ok("PostgreSQL is reachable")
        from backend.migrations_check import check_schema

        up_to_date, message = check_schema(engine)
        (ok if up_to_date else fail)(message)
    except Exception as exc:
        fail(f"Database check failed: {exc}\n          Is Docker running? Try: docker compose up -d")

# ── 4b. Production readiness (the same checklist the server logs at startup) ─
if os.environ.get("ENVIRONMENT", "development") != "development" and all(
    os.environ.get(key) for key in ("GROQ_API_KEY", "DATABASE_URL", "JWT_SECRET")
):
    from backend import production_checks

    findings = production_checks.current()
    for severity, message in findings:
        (fail if severity == "error" else warn)(message)
    if not findings:
        ok("production configuration looks right")

# ── 5. Voices (the same table the server uses) ───────────────────────────────
try:
    from backend.personalities import VOICES

    for voice_id, voice in VOICES.items():
        path = ROOT / voice["file"]
        if path.exists() and path.with_name(path.name + ".json").exists():
            ok(f"voice {voice_id:7s} {path.name} ({path.stat().st_size / 1_048_576:.0f} MB)")
        else:
            fail(f"voice {voice_id} is missing ({path.name}) — run: python scripts/download_voices.py")

    # The accents behind the speaking styles. Not required (Standard English works without them), so a missing
    # model is a warning: the styles it serves are simply hidden until it is installed.
    from backend.services import tts

    regional_missing = tts.missing_regional_models()
    for filename in tts.REGIONAL_FILES:
        if filename in regional_missing:
            warn(f"accent voice {filename} is missing, so the speaking styles that use it are unavailable — run: python scripts/download_voices.py")
        else:
            ok(f"accent voice {filename} ({tts.model_path(filename).stat().st_size / 1_048_576:.0f} MB)")
except Exception as exc:
    fail(f"Could not read the voice table: {exc}")

# ── 6. Groq ───────────────────────────────────────────────────────────────────
if os.environ.get("GROQ_API_KEY") and not args.skip_groq:
    try:
        from groq import Groq

        model = os.environ.get("LLM_ANALYSIS_MODEL", "openai/gpt-oss-120b")
        Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
            model=model, messages=[{"role": "user", "content": "hi"}], max_tokens=5,
        )
        ok(f"Groq API reachable (model {model})")
    except Exception as exc:
        fail(f"Groq API request failed: {exc}")

# ── 7. Microphone (only for local_client.py) ─────────────────────────────────
if args.local_client:
    try:
        import sounddevice as sd

        if any(d["max_input_channels"] > 0 for d in sd.query_devices()):
            ok(f"microphone: {sd.query_devices(kind='input')['name']}")
        else:
            fail("No microphone found")
    except Exception as exc:
        fail(f"Microphone check failed: {exc}")

# ── Summary ───────────────────────────────────────────────────────────────────
print()
if problems:
    print(f"[X]  {len(problems)} problem(s):")
    for problem in problems:
        print(f"     - {problem}")
    sys.exit(1)
print("[OK]  Setup looks good." + (f"  ({len(warnings)} warning(s) above)" if warnings else ""))
