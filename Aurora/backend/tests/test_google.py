"""Google OAuth: redirects, state/CSRF, one-time exchange codes, linking and takeover protection."""
from urllib.parse import parse_qs, urlparse

import pytest

from backend.database import SessionLocal
from backend.models.core import User
from backend.tests.conftest import PASSWORD, bearer

FRONTEND = "http://localhost:3000"


def _google_user(email="person@example.com", sub="google-sub-1", verified=True, name="Person", picture="https://img.example/p.png"):
    return {"google_id": sub, "email": email, "email_verified": verified, "name": name, "picture": picture}


@pytest.fixture
def google(monkeypatch):
    """Controls what 'Google' returns in the callback."""
    state = {"user": _google_user(), "fail": False}

    def exchange_code(code):
        if state["fail"]:
            from backend.services.google_oauth import GoogleOAuthError
            raise GoogleOAuthError("bad code")
        return "access-token"

    monkeypatch.setattr("backend.routers.google.exchange_code", exchange_code)
    monkeypatch.setattr("backend.routers.google.get_google_user", lambda token: state["user"])
    return state


def _begin(client, **params):
    """Starts the flow; returns (state, redirect_location)."""
    r = client.get("/api/auth/google", params=params, follow_redirects=False)
    assert r.status_code in (302, 307)
    loc = r.headers["location"]
    state = client.cookies.get("aura_oauth_state")
    return state, loc


def _callback(client, state, code="auth-code"):
    return client.get("/api/auth/google/callback", params={"code": code, "state": state}, follow_redirects=False)


def _exchange_code_from(location: str) -> str:
    assert location.startswith(f"{FRONTEND}/auth/google/callback?"), location
    return parse_qs(urlparse(location).query)["code"][0]


# ── Redirect + state ──────────────────────────────────────────────────────────

def test_login_redirects_to_google_with_a_state_cookie(client):
    r = client.get("/api/auth/google", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].startswith("https://accounts.google.com/")
    cookie = r.headers["set-cookie"].lower()
    assert "aura_oauth_state" in cookie and "httponly" in cookie
    assert "secure" not in cookie  # http redirect URI in dev


def test_state_cookie_is_secure_when_the_callback_is_https(monkeypatch):
    import importlib
    import backend.config as cfg

    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://api.example.com/api/auth/google/callback")
    assert importlib.reload(cfg).COOKIE_SECURE is True
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    importlib.reload(cfg)


def test_unconfigured_google_redirects_with_a_clear_error(client, monkeypatch):
    monkeypatch.setattr("backend.services.google_oauth.GOOGLE_CLIENT_ID", "")
    r = client.get("/api/auth/google", follow_redirects=False)
    assert r.headers["location"] == f"{FRONTEND}/login?error=google_not_configured"


def test_callback_without_matching_state_fails(client, google):
    r = client.get("/api/auth/google/callback", params={"code": "x", "state": "forged"}, follow_redirects=False)
    assert r.headers["location"] == f"{FRONTEND}/login?error=google_failed"
    r = client.get("/api/auth/google/callback", follow_redirects=False)
    assert "error=google_failed" in r.headers["location"]


def test_callback_fails_cleanly_when_google_errors(client, google):
    state, _ = _begin(client)
    google["fail"] = True
    assert _callback(client, state).headers["location"] == f"{FRONTEND}/login?error=google_failed"


def test_callback_rejects_an_unverified_google_email(client, google):
    state, _ = _begin(client)
    google["user"] = _google_user(verified=False)
    assert "error=google_failed" in _callback(client, state).headers["location"]


# ── Sign-in via one-time code (no session token in any URL) ───────────────────

def test_new_google_user_is_created_and_signs_in_through_a_one_time_code(client, google, db):
    state, _ = _begin(client)
    r = _callback(client, state)
    location = r.headers["location"]
    assert "access_token" not in location and "token=" not in location.replace("code=", "")  # no session in the URL
    code = _exchange_code_from(location)

    ex = client.post("/api/auth/google/exchange", json={"code": code})
    assert ex.status_code == 200
    body = ex.json()
    assert body["user"]["email"] == "person@example.com"
    assert body["user"]["google_linked"] is True and body["user"]["email_verified"] is True
    assert body["user"]["has_password"] is False
    assert client.get("/api/auth/me", headers=bearer(body["access_token"])).status_code == 200


def test_exchange_codes_are_single_use(client, google):
    state, _ = _begin(client)
    code = _exchange_code_from(_callback(client, state).headers["location"])
    assert client.post("/api/auth/google/exchange", json={"code": code}).status_code == 200
    assert client.post("/api/auth/google/exchange", json={"code": code}).status_code == 400


def test_exchange_rejects_garbage_and_session_tokens(client, user):
    assert client.post("/api/auth/google/exchange", json={"code": "not-a-real-code-at-all"}).status_code == 400
    # A normal session JWT is not an exchange code (purpose mismatch).
    assert client.post("/api/auth/google/exchange", json={"code": user["token"] + "x" * 5}).status_code == 400
    assert client.post("/api/auth/google/exchange", json={"code": user["token"]}).status_code == 400


def test_returning_google_user_signs_straight_in(client, google, db):
    state, _ = _begin(client)
    _callback(client, state)
    state, _ = _begin(client)
    code = _exchange_code_from(_callback(client, state).headers["location"])
    assert client.post("/api/auth/google/exchange", json={"code": code}).status_code == 200
    assert db.query(User).count() == 1


# ── Linking onto an existing password account ────────────────────────────────

def test_google_links_to_a_VERIFIED_password_account_and_keeps_the_password(client, google, make_user, outbox, db):
    make_user("person@example.com")
    client.post("/api/auth/verify-email", headers=bearer(client.post("/api/auth/login", json={"email": "person@example.com", "password": PASSWORD}).json()["access_token"]), json={"otp": outbox[0]["otp"]})

    state, _ = _begin(client)
    code = _exchange_code_from(_callback(client, state).headers["location"])
    body = client.post("/api/auth/google/exchange", json={"code": code}).json()

    assert body["user"]["google_linked"] is True and body["user"]["has_password"] is True
    assert client.post("/api/auth/login", json={"email": "person@example.com", "password": PASSWORD}).status_code == 200


def test_account_pre_hijack_is_blocked(client, google, make_user):
    """
    An attacker registers the victim's email (unverified) with a password they know.
    When the victim later signs in with Google, the attacker must NOT keep access.
    """
    attacker = make_user("person@example.com", password="attacker-knows-this-1")
    assert attacker["user"]["email_verified"] is False

    state, _ = _begin(client)
    code = _exchange_code_from(_callback(client, state).headers["location"])
    victim = client.post("/api/auth/google/exchange", json={"code": code}).json()

    assert victim["user"]["google_linked"] is True and victim["user"]["email_verified"] is True
    assert victim["user"]["has_password"] is False                               # attacker's password was discarded
    assert client.post("/api/auth/login", json={"email": "person@example.com", "password": "attacker-knows-this-1"}).status_code == 401
    assert client.get("/api/auth/me", headers=attacker["headers"]).status_code == 401   # their live session is revoked
    assert client.get("/api/auth/me", headers=bearer(victim["access_token"])).status_code == 200


# ── "Connect Google" from the profile (already signed in) ────────────────────

def test_link_code_requires_a_session(client):
    assert client.post("/api/auth/google/link-code").status_code == 401


def test_link_flow_connects_the_matching_google_account(client, google, user, db):
    google["user"] = _google_user(email=user["email"], sub="g-link-1")
    link_code = client.post("/api/auth/google/link-code", headers=user["headers"]).json()["link_code"]

    state, location = _begin(client, link_code=link_code)
    assert location.startswith("https://accounts.google.com/") and state.endswith(f":{user['user']['id']}")
    r = _callback(client, state)
    assert r.headers["location"] == f"{FRONTEND}/profile"

    me = client.get("/api/auth/me", headers=user["headers"]).json()
    assert me["google_linked"] is True and me["email_verified"] is True and me["has_password"] is True


def test_link_flow_refuses_a_different_google_email(client, google, user):
    google["user"] = _google_user(email="someone-else@example.com", sub="g-other")
    link_code = client.post("/api/auth/google/link-code", headers=user["headers"]).json()["link_code"]
    state, _ = _begin(client, link_code=link_code)
    assert _callback(client, state).headers["location"] == f"{FRONTEND}/profile?error=google_link_mismatch"
    assert client.get("/api/auth/me", headers=user["headers"]).json()["google_linked"] is False


def test_link_flow_refuses_a_google_account_already_used_elsewhere(client, google, make_user):
    first = make_user("first@example.com")
    second = make_user("second@example.com")
    for u in (first, second):
        google["user"] = _google_user(email=u["email"], sub="shared-google-sub")
        link_code = client.post("/api/auth/google/link-code", headers=u["headers"]).json()["link_code"]
        state, _ = _begin(client, link_code=link_code)
        location = _callback(client, state).headers["location"]
    assert location == f"{FRONTEND}/profile?error=google_link_conflict"


def test_a_bad_or_session_token_cannot_start_a_link(client, user):
    for bad in ("garbage", user["token"]):  # a session JWT must not work as a link code
        r = client.get("/api/auth/google", params={"link_code": bad}, follow_redirects=False)
        assert r.headers["location"] == f"{FRONTEND}/profile?error=google_failed"


# ── Disconnect ────────────────────────────────────────────────────────────────

def test_disconnect_rules(client, google, user):
    assert client.post("/api/auth/google/disconnect", headers=user["headers"]).status_code == 400  # nothing linked

    google["user"] = _google_user(email=user["email"])
    link_code = client.post("/api/auth/google/link-code", headers=user["headers"]).json()["link_code"]
    state, _ = _begin(client, link_code=link_code)
    _callback(client, state)
    r = client.post("/api/auth/google/disconnect", headers=user["headers"])
    assert r.status_code == 200 and r.json()["google_linked"] is False


def test_google_only_account_cannot_disconnect_until_it_has_a_password(client):
    from backend.services.auth import create_access_token

    with SessionLocal() as s:
        u = User(email="g@example.com", google_id="g-1", email_verified=True)
        s.add(u)
        s.commit()
        headers = bearer(create_access_token(u.id, u.token_version))
    assert client.post("/api/auth/google/disconnect", headers=headers).status_code == 400
    new = client.post("/api/auth/change-password", headers=headers, json={"new_password": "first-password-1"}).json()
    assert client.post("/api/auth/google/disconnect", headers=bearer(new["access_token"])).status_code == 200
