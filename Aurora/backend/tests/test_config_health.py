"""Health, options, CORS, request-size limits."""
import pytest

from backend.services import llm, tts


def test_health_basic(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["database"] == "connected" and body["groq_api"] == "skipped"


def test_health_full_pings_the_llm(client, monkeypatch):
    monkeypatch.setattr(llm, "ping", lambda: True)
    assert client.get("/health?full=true").json()["groq_api"] == "connected"
    monkeypatch.setattr(llm, "ping", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    assert client.get("/health?full=true").json()["groq_api"].startswith("error")


def test_options_lists_every_choice_and_defaults(client, ai):
    d = client.get("/api/config/options").json()
    assert {v["id"] for v in d["voices"]} == {"eida", "maya", "amy", "ryan", "alan", "lessac"}
    assert {"standard", "british", "irish"} <= {s["id"] for s in d["styles"]}
    assert {"casual", "interview", "travel"} <= {s["id"] for s in d["scenarios"]}
    assert [x["level"] for x in d["difficulties"]] == [1, 2, 3, 4, 5]
    assert d["defaults"] == {"voice": "amy", "style": "standard", "scenario": "casual"}


def test_options_hides_voices_that_are_not_installed(client, monkeypatch):
    monkeypatch.setattr(tts, "voice_available", lambda v: v not in ("ryan", "amy"))
    d = client.get("/api/config/options").json()
    ids = {v["id"] for v in d["voices"]}
    assert "ryan" not in ids and "amy" not in ids
    assert d["defaults"]["voice"] in ids   # the default falls back to one that exists


def test_tts_voice_files_come_from_personalities_not_a_second_list():
    from backend.personalities import VOICES

    assert set(tts.VOICE_FILES) == set(VOICES)
    assert tts.VOICE_FILES["lessac"] == "en_US-norman-medium.onnx"
    assert tts.VOICE_FILES["eida"] == "en_US-kristin-medium.onnx"


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_cors_allows_the_dev_frontend_origins(client, origin):
    r = client.options("/api/conversation/start", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization",
    })
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_other_origins(client):
    r = client.options("/api/conversation/start", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_origins_are_configurable(monkeypatch):
    import importlib
    import backend.config as cfg

    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com/, https://www.example.com")
    monkeypatch.setenv("FRONTEND_URL", "https://app.example.com")
    monkeypatch.setenv("ENVIRONMENT", "production")
    reloaded = importlib.reload(cfg)
    try:
        assert reloaded.CORS_ORIGINS == ["https://app.example.com", "https://www.example.com"]   # normalised, deduped, no localhost
    finally:
        monkeypatch.undo()
        importlib.reload(cfg)


def test_json_endpoints_reject_huge_bodies(client):
    r = client.post("/api/auth/login", content=b'{"email":"a@example.com","password":"' + b"x" * 1_200_000 + b'"}',
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_body_limit_also_counts_undeclared_chunked_bodies():
    """The middleware must not trust Content-Length: a chunked body has none."""
    import asyncio
    from backend.middleware import BodySizeLimitMiddleware

    sent = []

    async def app(scope, receive, send):
        while True:
            message = await receive()          # an app reading its body
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    chunks = [{"type": "http.request", "body": b"x" * 600, "more_body": True} for _ in range(3)] + [{"type": "http.request", "body": b"", "more_body": False}]

    async def receive():
        return chunks.pop(0)

    async def send(message):
        sent.append(message)

    mw = BodySizeLimitMiddleware(app, limits=[], default=1000)
    asyncio.run(mw({"type": "http", "path": "/x", "headers": []}, receive, send))
    assert sent[0]["status"] == 413
