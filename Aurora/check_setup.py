# check_setup.py (root level — run from Aurora/ with venv active)
"""
Run this to verify your Phase 0 setup is complete.
python check_setup.py
"""
import sys
import os

print(f"Python: {sys.version.split()[0]}")
print(f"Interpreter: {sys.executable}")
print()

problems = []

# ── 1. Virtual environment ────────────────────────────────────────────────────
in_venv = hasattr(sys, "real_prefix") or (
    hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
)
if not in_venv:
    problems.append("Not in venv — run: venv\\Scripts\\activate")
else:
    print("  OK  running inside venv")

# ── 2. Required packages ──────────────────────────────────────────────────────
packages = {
    "fastapi":        "fastapi",
    "uvicorn":        "uvicorn[standard]",
    "sqlalchemy":     "sqlalchemy",
    "alembic":        "alembic",
    "psycopg2":       "psycopg2-binary",
    "faster_whisper": "faster-whisper",
    "piper":          "piper-tts",
    "sounddevice":    "sounddevice",
    "numpy":          "numpy",
    "dotenv":         "python-dotenv",
    "groq":           "groq",
    "pydantic":       "pydantic",
}
for import_name, install_name in packages.items():
    try:
        __import__(import_name)
        print(f"  OK  {import_name}")
    except ImportError:
        problems.append(f"Missing '{import_name}' — pip install {install_name}")

# ── 3. .env file and required keys ───────────────────────────────────────────
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
load_dotenv()

required_env = ["GROQ_API_KEY", "DATABASE_URL"]
for key in required_env:
    val = os.environ.get(key)
    if not val:
        problems.append(f"{key} not set — check your .env file")
    else:
        masked = val[:8] + "..." if len(val) > 8 else "***"
        print(f"  OK  {key} = {masked}")

# ── 4. Groq API connectivity ──────────────────────────────────────────────────
groq_key = os.environ.get("GROQ_API_KEY")
if groq_key:
    try:
        # pyrefly: ignore [missing-import]
        from groq import Groq
        client = Groq(api_key=groq_key)
        client.chat.completions.create(
            model="openai/gpt-oss-120b",   # ← Fast model for health check
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        print("  OK  Groq API — connected (openai/gpt-oss-120b)")
    except Exception as e:
        problems.append(f"Groq API failed: {e}")

# ── 5. PostgreSQL connectivity ────────────────────────────────────────────────
db_url = os.environ.get("DATABASE_URL")
if db_url:
    try:
        # pyrefly: ignore [missing-import]
        from sqlalchemy import create_engine, text
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  OK  PostgreSQL — connected")
    except Exception as e:
        problems.append(
            f"PostgreSQL failed: {e}\n"
            "     Is Docker running? Try: docker compose up -d"
        )

# ── 6. Piper voice files ──────────────────────────────────────────────────────
voice_files = [
    "voices/en_US-amy-medium.onnx",
    "voices/en_US-lessac-medium.onnx",
    "voices/en_US-ryan-high.onnx",
    "voices/en_GB-alan-medium.onnx",
]
for vf in voice_files:
    if os.path.exists(vf):
        size_mb = os.path.getsize(vf) / 1_048_576
        print(f"  OK  {vf} ({size_mb:.0f} MB)")
    else:
        problems.append(f"Missing voice file: {vf}")

# ── 7. Microphone ─────────────────────────────────────────────────────────────
try:
    # pyrefly: ignore [missing-import]
    import sounddevice as sd
    devices = sd.query_devices()
    input_devices = [d for d in devices if d["max_input_channels"] > 0]
    if input_devices:
        default = sd.query_devices(kind="input")
        print(f"  OK  microphone — '{default['name']}'")
    else:
        problems.append("No input devices found — check microphone")
except Exception as e:
    problems.append(f"Microphone check failed: {e}")

# ── 8. Backend structure ──────────────────────────────────────────────────────
expected_files = [
    "backend/main.py",
    "backend/config.py",
    "backend/database.py",
    "backend/models/core.py",
    "backend/schemas/core.py",
    "backend/services/llm.py",
    "backend/services/stt.py",
    "backend/services/tts.py",
    "backend/routers/health.py",
    "backend/requirements.txt",
    ".env.example",
    "docker-compose.yml",
]
for f in expected_files:
    if os.path.exists(f):
        print(f"  OK  {f}")
    else:
        problems.append(f"Missing file: {f}")

# ── Summary ───────────────────────────────────────────────────────────────────
print()
if problems:
    print(f"[X]  {len(problems)} problem(s) found:")
    for p in problems:
        print(f"    - {p}")
    sys.exit(1)
else:
    print("[OK]  Everything checks out. Phase 0 complete - ready for Phase 1.")