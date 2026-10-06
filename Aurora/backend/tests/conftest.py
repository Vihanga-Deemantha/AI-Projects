"""
Test fixtures.

Safety first: before anything from `backend` is imported, the environment is
forced to a dedicated test database and dummy credentials. `load_dotenv()` in
backend/config.py never overrides variables that already exist, so a developer's
real .env (live Groq/Resend/Cloudinary keys, the dev database) can never leak
into a test run. All AI and email services are replaced with in-process fakes —
no network, no model files, no cost.

Needs a reachable Postgres (the project's `docker compose up -d`). The test
database is created on demand. Override with TEST_DATABASE_URL; its name must end
in `_test`.
"""
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://aura:aura_dev_pass@localhost:5432/aura_test"
)
_url = make_url(TEST_DATABASE_URL)
if not (_url.database or "").endswith("_test"):
    raise SystemExit(f"Refusing to run: TEST_DATABASE_URL database must end in '_test' (got {_url.database!r}).")

os.environ.update({
    "DATABASE_URL": TEST_DATABASE_URL,
    "GROQ_API_KEY": "test-groq-key",
    "JWT_SECRET": "test-jwt-secret-for-pytest-only-0123456789abcdef",
    "ENVIRONMENT": "development",
    "LOG_LEVEL": "WARNING",
    "RESEND_API_KEY": "",
    "CLOUDINARY_CLOUD_NAME": "",
    "CLOUDINARY_API_KEY": "",
    "CLOUDINARY_API_SECRET": "",
    "GOOGLE_CLIENT_ID": "test-google-client-id",
    "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
    "GOOGLE_REDIRECT_URI": "http://localhost:8000/api/auth/google/callback",
    "FRONTEND_URL": "http://localhost:3000",
    "CORS_ORIGINS": "",
    "PREWARM_MODELS": "0",
    "CHECK_MIGRATIONS_ON_STARTUP": "0",
    "STT_PROVIDER": "local",
    "RATE_LIMITS_ENABLED": "1",
    "BCRYPT_ROUNDS": "4",        # fast hashing; production uses 12
    "SQL_ECHO": "0",
    "SENTRY_DSN": "",
})


def _ensure_database() -> None:
    admin = create_engine(_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _url.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{_url.database}"'))
    except Exception as exc:  # connection refused, auth, ...
        raise SystemExit(
            f"Cannot reach Postgres for tests ({exc.__class__.__name__}). "
            "Start it with `docker compose up -d` (or set TEST_DATABASE_URL)."
        ) from exc
    finally:
        admin.dispose()


_ensure_database()

from fastapi.testclient import TestClient  # noqa: E402

import backend.models  # noqa: E402,F401  (registers every table)
from backend.database import Base, SessionLocal, engine  # noqa: E402
from backend.main import app  # noqa: E402
from backend.services import auth as auth_service  # noqa: E402
from backend.personalities import ACCENT_VOICES  # noqa: E402
from backend.services import llm, stt, tts  # noqa: E402
from backend.services.ratelimit import limiter  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    # The tables come from the models, not from migrations (test_migrations.py proves the two
    # agree), so mark the database as being at the latest revision, as a deployed one would be.
    # Otherwise /health, which checks the schema version, would report this DB as behind.
    from backend.migrations_check import head_revision

    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        ))
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": head_revision()})
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_state():
    """Every test starts with empty tables and fresh rate-limit counters."""
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    limiter.reset()
    yield


@pytest.fixture
def client():
    # Used as a context manager so one event loop lives for the whole test —
    # the fire-and-forget analysis task must survive between requests.
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


# ── Fakes for everything that would touch the network or a model file ─────────

class FakeAI:
    """Deterministic stand-in for Whisper, the Groq LLM and Piper."""

    def __init__(self):
        self.transcript = "Yesterday I go to the mall and I buy some clothes."
        self.duration = 4.2
        self.avg_logprob = -0.2
        self.words: list[dict] | None = None  # None -> derived from the transcript
        self.reply_tokens = ["That sounds like a busy day! ", "What did you buy?"]
        self.analysis_payload: dict | str = {
            "corrections": [{
                "category": "grammar", "subtype": "past_tense",
                "original": "I go to the mall", "correction": "I went to the mall",
                "explanation": "Use the simple past for finished actions.",
                "is_error": True, "severity": "high",
            }]
        }
        self.stt_error: Exception | None = None
        self.llm_error: Exception | None = None       # raised after `llm_error_after` tokens
        self.llm_error_after = 0
        self.tts_error: Exception | None = None
        self.analysis_error: Exception | None = None
        self.analysis_gate: threading.Event | None = None  # when set, analysis blocks until it is released
        self.summary: str | None = "You spoke with confidence and used some lovely expressions. Next time, watch your past tenses."
        self.summary_calls: list[list[dict]] = []
        self.stt_delay = 0.0
        self.stt_calls = 0
        self.llm_calls: list[list[dict]] = []      # messages given to the conversation LLM
        self.analysis_calls: list[list[dict]] = [] # messages given to the analysis LLM
        self.tts_calls: list[tuple[str, str]] = []
        self.tts_styles: list[str] = []            # the speaking style each spoken sentence was asked for

    def build_words(self) -> list[dict]:
        out, t = [], 0.0
        for token in self.transcript.split():
            out.append({"word": token, "start": round(t, 3), "end": round(t + 0.35, 3), "probability": 0.95})
            t += 0.4
        return out

    # -- patched callables ----------------------------------------------------
    def transcribe(self, path: str) -> dict:
        self.stt_calls += 1
        if self.stt_delay:
            time.sleep(self.stt_delay)
        if self.stt_error:
            raise self.stt_error
        words = self.words if self.words is not None else self.build_words()
        return {
            "text": self.transcript,
            "duration": self.duration,
            "words": words,
            "avg_logprob": self.avg_logprob,
            "latency_ms": 12.0,
        }

    def chat_stream(self, messages, *args, **kwargs):
        self.llm_calls.append(messages)
        for i, token in enumerate(self.reply_tokens):
            if self.llm_error and i >= self.llm_error_after:
                raise self.llm_error
            yield token
        if self.llm_error and self.llm_error_after >= len(self.reply_tokens):
            raise self.llm_error

    def chat_json(self, messages, *args, **kwargs) -> str:
        self.analysis_calls.append(messages)
        if self.analysis_gate is not None:
            self.analysis_gate.wait(timeout=10)
        if self.analysis_error:
            raise self.analysis_error
        payload = self.analysis_payload
        return payload if isinstance(payload, str) else json.dumps(payload)

    def chat(self, messages, *args, **kwargs) -> str:
        self.summary_calls.append(messages)
        if self.summary is None:
            raise RuntimeError("llm down")
        return self.summary

    def synthesize_text(self, text_: str, voice_id: str = "amy", style: str = "standard") -> bytes:
        self.tts_calls.append((text_, voice_id))
        self.tts_styles.append(style)
        if self.tts_error:
            raise self.tts_error
        return b"RIFF....WAVEfake-audio"

    def synthesize(self, text_: str, voice_id: str = "amy", length_scale: float | None = None, style: str = "standard") -> dict:
        self.tts_calls.append((text_, voice_id, length_scale))
        self.tts_styles.append(style)
        if self.tts_error:
            raise self.tts_error
        return {"audio_bytes": b"RIFF....WAVEword-audio", "latency_ms": 1.0}


@pytest.fixture
def ai(monkeypatch) -> FakeAI:
    fake = FakeAI()
    monkeypatch.setattr(stt, "transcribe", fake.transcribe)
    monkeypatch.setattr(llm, "chat_stream", fake.chat_stream)
    monkeypatch.setattr(llm, "chat_json", fake.chat_json)
    monkeypatch.setattr(llm, "chat", fake.chat)
    monkeypatch.setattr(tts, "synthesize_text", fake.synthesize_text)
    monkeypatch.setattr(tts, "synthesize", fake.synthesize)
    tts.word_audio.cache_clear()
    monkeypatch.setattr(tts, "voice_available", lambda voice_id: True)
    # No model files in tests: pretend every model is installed, so whether a companion can speak a style
    # depends only on the accent table (personalities.ACCENT_VOICES). The real availability logic still runs.
    monkeypatch.setattr(tts, "_model_installed", lambda filename: True)
    monkeypatch.setattr(tts, "_speaker_names", lambda filename: frozenset(
        spec["speaker"] for by_companion in ACCENT_VOICES.values() for spec in by_companion.values() if spec["speaker"]
    ))
    return fake


@pytest.fixture
def outbox(monkeypatch) -> list[dict]:
    """Captures every email instead of sending it: [{'kind', 'to', 'otp'}, ...]."""
    sent: list[dict] = []
    monkeypatch.setattr(auth_service, "send_reset_email", lambda to, otp: sent.append({"kind": "reset", "to": to, "otp": otp}))
    monkeypatch.setattr(auth_service, "send_verification_email", lambda to, otp: sent.append({"kind": "verification", "to": to, "otp": otp}))
    return sent


# ── Small helpers used across test modules ────────────────────────────────────

PASSWORD = "correct-horse-battery"


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_user(client, outbox):
    """make_user("a@example.com") -> {'email', 'password', 'token', 'headers', 'user'}"""

    def _make(email: str = "learner@example.com", password: str = PASSWORD, display_name: str | None = "Learner") -> dict:
        r = client.post("/api/auth/signup", json={"email": email, "password": password, "display_name": display_name})
        assert r.status_code == 201, r.text
        body = r.json()
        return {
            "email": email, "password": password, "token": body["access_token"],
            "headers": bearer(body["access_token"]), "user": body["user"],
        }

    return _make


@pytest.fixture
def user(make_user) -> dict:
    return make_user()


@pytest.fixture
def start_session(client):
    def _start(headers: dict, **form) -> str:
        r = client.post("/api/conversation/start", headers=headers, data=form)
        assert r.status_code == 200, r.text
        return r.json()["conversation_id"]

    return _start


@pytest.fixture
def post_turn(client):
    """Sends one spoken turn and returns (response, [events])."""

    def _post(headers: dict, conversation_id: str, audio: bytes = b"RIFFfakeaudio", filename: str = "turn.webm"):
        r = client.post(
            "/api/conversation/message-stream",
            headers=headers,
            data={"conversation_id": conversation_id},
            files={"audio_file": (filename, audio, "audio/webm")},
        )
        events = [json.loads(line) for line in r.text.splitlines() if line.strip()] if r.status_code == 200 else []
        return r, events

    return _post


def wait_until(predicate, timeout: float = 5.0, interval: float = 0.05):
    """Polls `predicate` until it returns something truthy (returns it) or the timeout hits (returns None)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


@pytest.fixture
def wait_for_analysis():
    """Blocks until no user turn in the conversation is still 'pending'."""
    from backend.models.core import Message

    def _wait(conversation_id: str, timeout: float = 5.0) -> bool:
        def done():
            with SessionLocal() as s:
                pending = s.query(Message).filter_by(conversation_id=conversation_id, analysis_status="pending").count()
            return pending == 0

        return bool(wait_until(done, timeout))

    return _wait
