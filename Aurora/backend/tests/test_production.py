"""Production readiness: the startup checklist, the health endpoint, and coping with a rate-limited LLM."""
import asyncio
import logging
from types import SimpleNamespace

import httpx
import pytest
from groq import APIConnectionError, RateLimitError

import backend.main as main_module
from backend import config, production_checks
from backend.database import get_db
from backend.models.core import Message
from backend.routers import health as health_router
from backend.services import llm, stt, tts


def rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return RateLimitError("Rate limit reached for org_secret123", response=httpx.Response(429, request=request), body=None)


# ── The production checklist ──────────────────────────────────────────────────

GOOD = dict(
    jwt_secret="x7Kq9mPz2Wv4Rt8Yb1Nc5Hd3Jf6Lg0Sa_UeOiTyQ",
    frontend_url="https://app.example.com",
    cors_origins=["https://app.example.com"],
    google_client_id="client-id",
    google_redirect_uri="https://api.example.com/api/auth/google/callback",
    resend_api_key="re_live_key",
    email_from="AURA <hello@example.com>",
    cloudinary_configured=True,
    rate_limits_enabled=True,
    sql_echo=False,
    log_level="INFO",
    sentry_dsn="https://key@sentry.example.com/1",
)


def found(**overrides):
    return production_checks.problems(**{**GOOD, **overrides})


def test_a_well_configured_deployment_has_no_findings():
    assert found() == []


@pytest.mark.parametrize("overrides, severity, fragment", [
    (dict(jwt_secret="short"), "error", "JWT_SECRET is shorter"),
    (dict(jwt_secret="please-change-this-to-a-long-random-value-1234"), "error", "placeholder"),
    (dict(frontend_url="http://localhost:3000"), "error", "FRONTEND_URL still points at localhost"),
    (dict(frontend_url="http://127.0.0.1:3000/"), "error", "FRONTEND_URL still points at localhost"),
    (dict(frontend_url="http://app.example.com"), "warning", "isn't https"),
    (dict(cors_origins=["https://app.example.com", "http://localhost:3000"]), "warning", "CORS_ORIGINS includes a localhost"),
    (dict(google_redirect_uri="http://api.example.com/api/auth/google/callback"), "error", "GOOGLE_REDIRECT_URI isn't https"),
    (dict(resend_api_key=""), "error", "RESEND_API_KEY is not set"),
    (dict(email_from="noreply@aura.app"), "warning", "EMAIL_FROM is a default or test sender"),
    (dict(email_from="Onboarding@Resend.dev"), "warning", "EMAIL_FROM is a default or test sender"),
    (dict(email_from=""), "warning", "EMAIL_FROM is a default or test sender"),
    (dict(cloudinary_configured=False), "warning", "Cloudinary isn't configured"),
    (dict(sentry_dsn=""), "warning", "SENTRY_DSN isn't set"),
    (dict(rate_limits_enabled=False), "error", "RATE_LIMITS_ENABLED is off"),
    (dict(sql_echo=True), "warning", "SQL_ECHO is on"),
    (dict(log_level="DEBUG"), "warning", "LOG_LEVEL is DEBUG"),
])
def test_each_misconfiguration_is_reported_with_the_right_severity(overrides, severity, fragment):
    findings = found(**overrides)
    assert len(findings) == 1, findings
    assert findings[0][0] == severity and fragment in findings[0][1]


def test_the_secret_length_boundary_is_32_characters():
    assert [s for s, _ in found(jwt_secret="a" * 31)] == ["error"]
    assert found(jwt_secret="a" * 32) == []


def test_google_settings_are_only_judged_when_google_sign_in_is_in_use():
    assert found(google_client_id="", google_redirect_uri="http://localhost:8000/api/auth/google/callback") == []


def test_only_real_localhost_addresses_count_as_local():
    assert production_checks._is_local("http://localhost:3000")
    assert production_checks._is_local("http://127.0.0.1")
    assert production_checks._is_local("http://[::1]:3000")
    assert production_checks._is_local("https://app.localhost")
    assert not production_checks._is_local("https://localhost.example.com")
    assert not production_checks._is_local("https://mylocalhost.dev")
    assert found(frontend_url="https://localhost.example.com") == []


def test_several_problems_are_all_reported():
    findings = found(jwt_secret="short", resend_api_key="", rate_limits_enabled=False)
    assert [s for s, _ in findings].count("error") == 3


def test_run_logs_each_finding_at_its_severity_and_returns_them(monkeypatch, caplog):
    monkeypatch.setattr(config, "RATE_LIMITS_ENABLED", False)
    monkeypatch.setattr(config, "SQL_ECHO", True)
    with caplog.at_level(logging.INFO, logger="aura.production"):
        result = production_checks.run()
    by_text = {r.getMessage(): r.levelno for r in caplog.records}
    assert any("RATE_LIMITS_ENABLED" in m and level == logging.ERROR for m, level in by_text.items())
    assert any("SQL_ECHO" in m and level == logging.WARNING for m, level in by_text.items())
    assert ("error", next(m for s, m in result if "RATE_LIMITS_ENABLED" in m)) in result


def test_run_says_so_when_everything_is_fine(monkeypatch, caplog):
    settings = dict(
        JWT_SECRET=GOOD["jwt_secret"], FRONTEND_URL=GOOD["frontend_url"], CORS_ORIGINS=GOOD["cors_origins"],
        GOOGLE_CLIENT_ID=GOOD["google_client_id"], GOOGLE_REDIRECT_URI=GOOD["google_redirect_uri"],
        RESEND_API_KEY=GOOD["resend_api_key"], EMAIL_FROM=GOOD["email_from"], CLOUDINARY_CLOUD_NAME="c",
        CLOUDINARY_API_KEY="k", CLOUDINARY_API_SECRET="s", RATE_LIMITS_ENABLED=True, SQL_ECHO=False,
        LOG_LEVEL="INFO", SENTRY_DSN=GOOD["sentry_dsn"],
    )
    for name, value in settings.items():
        monkeypatch.setattr(config, name, value)
    with caplog.at_level(logging.INFO, logger="aura.production"):
        assert production_checks.run() == []
    assert "no configuration problems" in caplog.text


def _start_and_stop_app(monkeypatch):
    """Runs the app's real startup/shutdown with the heavy parts (model loading) switched off."""
    monkeypatch.setattr(main_module, "PREWARM_MODELS", False)

    async def go():
        async with main_module.lifespan(main_module.app):
            pass

    asyncio.run(go())


def test_startup_runs_the_checklist_outside_development(monkeypatch):
    calls = []
    monkeypatch.setattr(main_module, "IS_DEVELOPMENT", False)
    monkeypatch.setattr(production_checks, "run", lambda: calls.append(1) or [])
    _start_and_stop_app(monkeypatch)
    assert calls == [1]


def test_startup_skips_the_checklist_in_development(monkeypatch):
    calls = []
    monkeypatch.setattr(main_module, "IS_DEVELOPMENT", True)
    monkeypatch.setattr(production_checks, "run", lambda: calls.append(1) or [])
    _start_and_stop_app(monkeypatch)
    assert calls == []


def test_findings_never_stop_the_app_from_starting(monkeypatch):
    monkeypatch.setattr(main_module, "IS_DEVELOPMENT", False)
    monkeypatch.setattr(production_checks, "run", lambda: [("error", "everything is wrong")])
    _start_and_stop_app(monkeypatch)       # no exception


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_reports_the_schema_and_the_speech_models(client):
    r = client.get("/health")
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok"
    assert body["migrations"] == "up to date"
    assert body["speech"]["stt"]["provider"] in ("local", "groq") and isinstance(body["speech"]["stt"]["ready"], bool)
    voices = body["speech"]["voices"]
    assert set(voices) == {"installed", "total", "loaded", "missing", "regional"} and voices["total"] == 6
    assert voices["installed"] + len(voices["missing"]) == voices["total"]
    assert set(voices["regional"]) == {"installed", "total"} and voices["regional"]["total"] >= 1


def test_a_database_outage_is_a_503_and_leaks_no_details(client):
    class Down:
        def execute(self, *a, **k):
            raise RuntimeError("could not connect to server at db.internal.example with password hunter2")

        def close(self):
            pass

    def down():
        yield Down()

    client.app.dependency_overrides[get_db] = down
    try:
        r = client.get("/health")
    finally:
        client.app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded" and body["database"] == "error: RuntimeError" and body["migrations"] == "unknown"
    assert "hunter2" not in r.text and "db.internal" not in r.text


def test_a_database_behind_the_code_is_a_503(client, monkeypatch):
    monkeypatch.setattr(health_router, "check_schema", lambda engine: (False, "Database schema is old, code expects new"))
    r = client.get("/health")
    assert r.status_code == 503 and r.json()["migrations"] == "behind" and r.json()["status"] == "degraded"
    assert "expects" not in r.text                                         # the detail goes to the log, not the response


def test_not_being_able_to_read_the_schema_is_a_503(client, monkeypatch):
    monkeypatch.setattr(health_router, "check_schema", lambda engine: (_ for _ in ()).throw(RuntimeError("boom")))
    r = client.get("/health")
    assert r.status_code == 503 and r.json()["migrations"] == "error: RuntimeError"


def test_no_voices_installed_means_the_coach_cannot_speak(client, monkeypatch):
    monkeypatch.setattr(tts, "status", lambda: {"installed": 0, "total": 6, "loaded": 0, "missing": ["amy"] * 6})
    assert client.get("/health").status_code == 503


def test_some_missing_voices_still_count_as_healthy(client, monkeypatch):
    monkeypatch.setattr(tts, "status", lambda: {"installed": 4, "total": 6, "loaded": 4, "missing": ["ryan", "alan"]})
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["speech"]["voices"]["missing"] == ["ryan", "alan"]


def test_a_groq_failure_is_a_503_only_when_it_was_asked_about(client, monkeypatch):
    monkeypatch.setattr(llm, "ping", lambda: (_ for _ in ()).throw(RuntimeError("401 key gsk_secret")))
    assert client.get("/health").status_code == 200                          # the fast check never calls Groq
    r = client.get("/health?full=true")
    assert r.status_code == 503 and r.json()["groq_api"] == "error: RuntimeError" and "gsk_secret" not in r.text


def test_being_rate_limited_by_groq_is_not_an_outage(client, monkeypatch):
    monkeypatch.setattr(llm, "ping", lambda: (_ for _ in ()).throw(rate_limit_error()))
    r = client.get("/health?full=true")
    assert r.status_code == 200 and r.json()["groq_api"] == "rate limited" and r.json()["status"] == "ok"
    assert "org_secret123" not in r.text


def test_a_working_groq_is_connected(client, monkeypatch):
    monkeypatch.setattr(llm, "ping", lambda: True)
    r = client.get("/health?full=true")
    assert r.status_code == 200 and r.json()["groq_api"] == "connected"


def test_speech_status_helpers(monkeypatch):
    monkeypatch.setattr(stt, "STT_PROVIDER", "groq")
    assert stt.status() == {"provider": "groq", "ready": True}
    monkeypatch.setattr(stt, "STT_PROVIDER", "local")
    monkeypatch.setattr(stt, "_model", None)
    assert stt.status() == {"provider": "local", "ready": False}
    monkeypatch.setattr(stt, "_model", object())
    assert stt.status() == {"provider": "local", "ready": True}

    monkeypatch.setattr(tts, "available_voices", lambda: ["amy", "alan"])
    monkeypatch.setattr(tts, "missing_voices", lambda: ["ryan"])
    monkeypatch.setattr(tts, "missing_regional_models", lambda: ["en_GB-vctk-medium.onnx"])
    # models are cached by file; only the companions' own voices count as "loaded" (a regional model is extra)
    monkeypatch.setattr(tts, "_voice_cache", {"en_US-amy-medium.onnx": object(), "en_GB-vctk-medium.onnx": object()})
    assert tts.status() == {
        "installed": 2, "total": len(tts.VOICE_FILES), "loaded": 1, "missing": ["ryan"],
        "regional": {"installed": len(tts.REGIONAL_FILES) - 1, "total": len(tts.REGIONAL_FILES)},
    }


# ── A rate-limited LLM ────────────────────────────────────────────────────────

def test_only_rate_limits_are_recognised_as_rate_limits():
    assert llm.is_rate_limited(rate_limit_error())
    assert not llm.is_rate_limited(RuntimeError("429"))
    assert not llm.is_rate_limited(APIConnectionError(request=httpx.Request("POST", "https://api.groq.com")))


def test_a_rate_limited_reply_tells_the_learner_to_wait_and_keeps_their_turn(user, start_session, ai, post_turn, db, caplog):
    ai.llm_error = rate_limit_error()
    with caplog.at_level(logging.WARNING):
        _, events = post_turn(user["headers"], start_session(user["headers"]))
    types = [e["type"] for e in events]
    assert types[0] == "transcript" and types[-2:] == ["error", "done"]
    assert "very busy" in events[-2]["message"] and "try again" in events[-2]["message"].lower()
    assert "org_secret123" not in events[-2]["message"]
    assert [m.role for m in db.query(Message).all()] == ["user"]
    # expected under load, so it is a one-line warning, not a stack trace
    assert not [r for r in caplog.records if r.exc_info and "aura.conversation" in r.name]


def test_other_llm_failures_keep_the_generic_message(user, start_session, ai, post_turn):
    ai.llm_error = RuntimeError("boom")
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert "couldn't respond" in events[-2]["message"] and "very busy" not in events[-2]["message"]


def test_a_rate_limited_analysis_is_marked_failed_with_a_warning_not_a_stack_trace(
    client, user, start_session, ai, post_turn, wait_for_analysis, db, caplog
):
    ai.analysis_error = rate_limit_error()
    cid = start_session(user["headers"])
    with caplog.at_level(logging.WARNING):
        post_turn(user["headers"], cid)
        assert wait_for_analysis(cid)
    assert db.query(Message).filter_by(role="user").one().analysis_status == "failed"
    assert any("rate-limiting" in r.getMessage() for r in caplog.records)
    assert not [r for r in caplog.records if r.exc_info and "aura.analysis" in r.name]


def test_a_genuine_analysis_failure_still_logs_the_stack_trace(user, start_session, ai, post_turn, wait_for_analysis, caplog):
    ai.analysis_error = RuntimeError("bug")
    cid = start_session(user["headers"])
    with caplog.at_level(logging.WARNING):
        post_turn(user["headers"], cid)
        assert wait_for_analysis(cid)
    assert [r for r in caplog.records if r.exc_info and "aura.analysis" in r.name]


class FakeGroq:
    """Records how a chat call was made: with which retry setting, and with which arguments."""

    def __init__(self):
        self.retries = "not set"
        self.kwargs = {}
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def with_options(self, **options):
        self.retries = options.get("max_retries", "not set")
        return self

    def _create(self, **kwargs):
        self.kwargs = kwargs
        message = SimpleNamespace(content='{"corrections": []}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message, delta=SimpleNamespace(content="hi"))])


def test_the_background_analysis_waits_out_rate_limits_but_a_live_reply_does_not(monkeypatch):
    monkeypatch.setattr(llm, "LLM_ANALYSIS_RETRIES", 7)
    fake = FakeGroq()
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    assert llm.chat_json([{"role": "user", "content": "hi"}]) == '{"corrections": []}'
    assert fake.retries == 7 and fake.kwargs["response_format"] == {"type": "json_object"}

    fake.retries = "not set"
    llm.chat([{"role": "user", "content": "hi"}])
    assert fake.retries == "not set"                         # live calls keep the SDK's short default


def test_the_retry_budget_is_configurable_and_never_negative():
    assert config.LLM_ANALYSIS_RETRIES >= 0
