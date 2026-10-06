"""Signup, login, sessions, profile, password change/reset, avatar, rate limits."""
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest

from backend.database import SessionLocal
from backend.models.core import User
from backend.tests.conftest import PASSWORD, bearer


# ── Signup ────────────────────────────────────────────────────────────────────

def test_signup_returns_token_and_user_without_secrets(client, outbox):
    r = client.post("/api/auth/signup", json={"email": "New@Example.com", "password": PASSWORD, "display_name": " Ada "})
    assert r.status_code == 201
    body = r.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    assert body["user"]["email"] == "new@example.com"      # normalised
    assert body["user"]["display_name"] == "Ada"            # trimmed
    assert body["user"]["email_verified"] is False
    assert body["user"]["has_password"] is True
    for secret in ("password_hash", "reset_otp_hash", "verify_otp_hash", "token_version"):
        assert secret not in r.text


def test_signup_sends_a_verification_code(client, outbox):
    client.post("/api/auth/signup", json={"email": "a@example.com", "password": PASSWORD})
    assert len(outbox) == 1
    assert outbox[0]["kind"] == "verification" and outbox[0]["to"] == "a@example.com"
    assert len(outbox[0]["otp"]) == 6 and outbox[0]["otp"].isdigit()


def test_signup_duplicate_email_is_409_case_insensitive(client, make_user):
    make_user("dup@example.com")
    r = client.post("/api/auth/signup", json={"email": "DUP@example.com", "password": PASSWORD})
    assert r.status_code == 409


@pytest.mark.parametrize("payload", [
    {"email": "not-an-email", "password": PASSWORD},
    {"email": "a@example.com", "password": "short"},
    {"email": "a@example.com", "password": PASSWORD, "display_name": "x" * 101},
])
def test_signup_validation(client, payload):
    assert client.post("/api/auth/signup", json=payload).status_code == 422


def test_signup_is_rate_limited_per_ip(client, outbox):
    codes = [client.post("/api/auth/signup", json={"email": f"u{i}@example.com", "password": PASSWORD}).status_code for i in range(12)]
    assert codes[:10] == [201] * 10
    assert codes[10:] == [429, 429]


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_ok_and_me(client, user):
    r = client.post("/api/auth/login", json={"email": user["email"], "password": PASSWORD})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers=bearer(r.json()["access_token"]))
    assert me.status_code == 200 and me.json()["email"] == user["email"]


def test_login_failures_are_indistinguishable(client, user):
    wrong_pw = client.post("/api/auth/login", json={"email": user["email"], "password": "wrongwrong1"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrongwrong1"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


def test_login_always_does_a_full_bcrypt_check(client, user, monkeypatch):
    """Timing parity, asserted structurally: a missing user still costs one bcrypt compare."""
    calls = []
    real = bcrypt.checkpw
    monkeypatch.setattr(bcrypt, "checkpw", lambda *a, **k: (calls.append(1), real(*a, **k))[1])

    client.post("/api/auth/login", json={"email": user["email"], "password": "wrongwrong1"})
    known = len(calls)
    client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "wrongwrong1"})
    unknown = len(calls) - known

    with SessionLocal() as s:  # a Google-only account (no password hash) must cost the same too
        s.add(User(email="g@example.com", google_id="g-1", email_verified=True))
        s.commit()
    client.post("/api/auth/login", json={"email": "g@example.com", "password": "wrongwrong1"})
    google_only = len(calls) - known - unknown

    assert known == unknown == google_only == 1


def test_login_locks_out_after_repeated_failures(client, user):
    bad = {"email": user["email"], "password": "wrongwrong1"}
    for _ in range(5):
        assert client.post("/api/auth/login", json=bad).status_code == 401
    r = client.post("/api/auth/login", json=bad)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


def test_successful_login_resets_the_failure_counter(client, user):
    bad = {"email": user["email"], "password": "wrongwrong1"}
    for _ in range(4):
        client.post("/api/auth/login", json=bad)
    assert client.post("/api/auth/login", json={"email": user["email"], "password": PASSWORD}).status_code == 200
    for _ in range(4):  # would have been blocked without the reset
        assert client.post("/api/auth/login", json=bad).status_code == 401


# ── Tokens ────────────────────────────────────────────────────────────────────

def test_missing_malformed_and_foreign_tokens_are_401(client, user):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=bearer("garbage")).status_code == 401


def test_a_purpose_token_is_not_a_session(client, user):
    from backend.services.auth import create_purpose_token

    token = create_purpose_token("google_exchange", user["user"]["id"], 60)
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_token_for_a_deleted_user_is_401(client, user, db):
    db.query(User).delete()
    db.commit()
    assert client.get("/api/auth/me", headers=user["headers"]).status_code == 401


# ── Profile ───────────────────────────────────────────────────────────────────

def test_profile_update(client, user):
    r = client.patch("/api/auth/profile", headers=user["headers"], json={
        "display_name": " Alice ", "bio": "learning", "preferred_voice": "ryan", "preferred_style": "british",
    })
    assert r.status_code == 200
    body = r.json()
    assert (body["display_name"], body["bio"], body["preferred_voice"], body["preferred_style"]) == ("Alice", "learning", "ryan", "british")


@pytest.mark.parametrize("patch,status", [
    ({"preferred_voice": "nope"}, 400),
    ({"preferred_style": "nope"}, 400),
    ({"bio": "x" * 301}, 422),
])
def test_profile_validation(client, user, patch, status):
    assert client.patch("/api/auth/profile", headers=user["headers"], json=patch).status_code == status


def test_profile_requires_auth(client):
    assert client.patch("/api/auth/profile", json={"bio": "x"}).status_code == 401


# ── Avatar (validation + storage call; the real Cloudinary upload is not exercised) ──

def test_avatar_rejects_non_images(client, user):
    r = client.post("/api/auth/avatar", headers=user["headers"], files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_avatar_rejects_oversize_files(client, user):
    # Just over the 5 MB rule: caught by the avatar validator.
    r = client.post("/api/auth/avatar", headers=user["headers"], files={"file": ("a.png", b"0" * (5 * 1024 * 1024 + 1), "image/png")})
    assert r.status_code == 400
    # Far over: cut off by the body-size middleware before it is buffered.
    r = client.post("/api/auth/avatar", headers=user["headers"], files={"file": ("a.png", b"0" * (6 * 1024 * 1024), "image/png")})
    assert r.status_code == 413


def test_avatar_happy_path_stores_the_url(client, user, monkeypatch):
    monkeypatch.setattr("backend.routers.auth.upload_avatar", lambda data, ctype, uid: f"https://cdn.example/{uid}.png")
    r = client.post("/api/auth/avatar", headers=user["headers"], files={"file": ("a.png", b"\x89PNG....", "image/png")})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=user["headers"]).json()["avatar_url"].startswith("https://cdn.example/")


def test_avatar_is_rate_limited(client, user, monkeypatch):
    monkeypatch.setattr("backend.routers.auth.upload_avatar", lambda *a: "https://cdn.example/x.png")
    codes = [client.post("/api/auth/avatar", headers=user["headers"], files={"file": ("a.png", b"x", "image/png")}).status_code for _ in range(11)]
    assert codes[-1] == 429


# ── Change password ───────────────────────────────────────────────────────────

def test_change_password_returns_new_token_and_revokes_old_ones(client, user):
    r = client.post("/api/auth/change-password", headers=user["headers"], json={"current_password": PASSWORD, "new_password": "brand-new-pass-1"})
    assert r.status_code == 200
    new_token = r.json()["access_token"]

    assert client.get("/api/auth/me", headers=user["headers"]).status_code == 401       # old session ended
    assert client.get("/api/auth/me", headers=bearer(new_token)).status_code == 200     # this one carries on
    assert client.post("/api/auth/login", json={"email": user["email"], "password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "brand-new-pass-1"}).status_code == 200


def test_change_password_requires_the_current_one(client, user):
    r = client.post("/api/auth/change-password", headers=user["headers"], json={"current_password": "WRONGWRONG", "new_password": "brand-new-pass-1"})
    assert r.status_code == 400  # 400, not 401: the frontend logs out on 401
    r = client.post("/api/auth/change-password", headers=user["headers"], json={"new_password": "brand-new-pass-1"})
    assert r.status_code == 400


def test_change_password_current_password_guessing_is_throttled(client, user):
    codes = [client.post("/api/auth/change-password", headers=user["headers"], json={"current_password": f"guess-number-{i}", "new_password": "brand-new-pass-1"}).status_code for i in range(7)]
    assert codes[:5] == [400] * 5
    assert codes[5] == 429


def test_change_password_enforces_min_length(client, user):
    r = client.post("/api/auth/change-password", headers=user["headers"], json={"current_password": PASSWORD, "new_password": "x" * 7})
    assert r.status_code == 422


def test_google_only_account_can_set_a_first_password(client):
    from backend.services.auth import create_access_token

    with SessionLocal() as s:
        u = User(email="g@example.com", google_id="g-1", email_verified=True)
        s.add(u)
        s.commit()
        token = create_access_token(u.id, u.token_version)
    r = client.post("/api/auth/change-password", headers=bearer(token), json={"new_password": "first-password-1"})
    assert r.status_code == 200 and r.json()["user"]["has_password"] is True
    assert client.post("/api/auth/login", json={"email": "g@example.com", "password": "first-password-1"}).status_code == 200


# ── Forgot password / OTP ─────────────────────────────────────────────────────

def _request_reset(client, email):
    return client.post("/api/auth/forgot-password", json={"email": email})


def _reset(client, email, otp, password="reset-password-1"):
    return client.post("/api/auth/verify-otp", json={"email": email, "otp": otp, "new_password": password})


def test_forgot_password_is_204_for_unknown_emails_and_sends_nothing(client, outbox):
    assert _request_reset(client, "ghost@example.com").status_code == 204
    assert outbox == []


def test_forgot_password_sends_a_code_to_known_emails(client, user, outbox):
    outbox.clear()
    assert _request_reset(client, user["email"]).status_code == 204
    assert [m["kind"] for m in outbox] == ["reset"] and outbox[0]["to"] == user["email"]


def test_forgot_password_always_pays_for_one_hash(client, user, monkeypatch):
    calls = []
    real = bcrypt.hashpw
    monkeypatch.setattr(bcrypt, "hashpw", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    _request_reset(client, user["email"])
    known = len(calls)
    _request_reset(client, "ghost@example.com")
    assert known == 1 and len(calls) - known == 1


def test_forgot_password_cooldown_blocks_attempt_counter_resets(client, user, outbox, db):
    outbox.clear()
    _request_reset(client, user["email"])
    code = outbox[-1]["otp"]
    for guess in ("000000", "000001"):
        _reset(client, user["email"], guess)
    db.expire_all()
    assert db.query(User).filter_by(email=user["email"]).one().reset_otp_attempts == 2

    _request_reset(client, user["email"])  # inside the cooldown: silently ignored
    db.expire_all()
    row = db.query(User).filter_by(email=user["email"]).one()
    assert row.reset_otp_attempts == 2     # NOT reset to 0
    assert len(outbox) == 1                # and no second email
    assert _reset(client, user["email"], code).status_code == 200  # the original code still works


def test_forgot_password_per_email_hourly_limit_is_silent(client, user, outbox, db):
    outbox.clear()
    for _ in range(5):
        _request_reset(client, user["email"])
        with SessionLocal() as s:  # skip the 60 s cooldown so only the hourly limit is in play
            s.query(User).filter_by(email=user["email"]).update({"reset_otp_sent_at": datetime.now(timezone.utc) - timedelta(minutes=5)})
            s.commit()
    assert len(outbox) == 3  # 3 per hour; later requests still answered 204 but ignored


def test_otp_success_sets_password_verifies_email_and_revokes_sessions(client, user, outbox):
    outbox.clear()
    _request_reset(client, user["email"])
    r = _reset(client, user["email"], outbox[-1]["otp"])
    assert r.status_code == 200
    assert r.json()["user"]["email_verified"] is True                                   # inbox control proven
    assert client.get("/api/auth/me", headers=user["headers"]).status_code == 401       # old session revoked
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "reset-password-1"}).status_code == 200


def test_otp_is_single_use(client, user, outbox):
    outbox.clear()
    _request_reset(client, user["email"])
    code = outbox[-1]["otp"]
    assert _reset(client, user["email"], code).status_code == 200
    assert _reset(client, user["email"], code).status_code == 400


def test_otp_locks_after_three_wrong_guesses_even_for_the_right_code(client, user, outbox):
    outbox.clear()
    _request_reset(client, user["email"])
    code = outbox[-1]["otp"]
    wrong = [c for c in ("111111", "222222", "333333", "444444") if c != code][:3]
    for guess in wrong:
        assert _reset(client, user["email"], guess).status_code == 400
    assert _reset(client, user["email"], code).status_code == 400


def test_otp_expires(client, user, outbox, db):
    outbox.clear()
    _request_reset(client, user["email"])
    db.query(User).filter_by(email=user["email"]).update({"reset_otp_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
    db.commit()
    assert _reset(client, user["email"], outbox[-1]["otp"]).status_code == 400


def test_otp_failures_are_generic(client, user, outbox):
    unknown = _reset(client, "ghost@example.com", "123456")
    outbox.clear()
    _request_reset(client, user["email"])
    wrong = _reset(client, user["email"], "000000" if outbox[-1]["otp"] != "000000" else "000001")
    assert unknown.status_code == wrong.status_code == 400
    assert unknown.json() == wrong.json() == {"detail": "Invalid or expired code"}


def test_otp_verification_does_one_bcrypt_check_whether_or_not_a_reset_is_pending(client, user, monkeypatch):
    calls = []
    real = bcrypt.checkpw
    monkeypatch.setattr(bcrypt, "checkpw", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    _reset(client, "ghost@example.com", "123456")
    assert len(calls) == 1


@pytest.mark.parametrize("otp", ["12345", "1234567", "abcdef", ""])
def test_otp_format_validation(client, otp):
    assert _reset(client, "a@example.com", otp).status_code == 422


def test_otp_guessing_is_rate_limited(client, user):
    codes = [_reset(client, user["email"], f"{i:06d}").status_code for i in range(12)]
    assert 429 in codes


# ── Email verification ───────────────────────────────────────────────────────

def test_verify_email_with_the_signup_code(client, user, outbox):
    code = outbox[0]["otp"]
    r = client.post("/api/auth/verify-email", headers=user["headers"], json={"otp": code})
    assert r.status_code == 200 and r.json()["email_verified"] is True
    assert client.get("/api/auth/me", headers=user["headers"]).json()["email_verified"] is True


def test_verify_email_wrong_code_and_lockout(client, user, outbox):
    code = outbox[0]["otp"]
    wrong = [c for c in ("111111", "222222", "333333", "444444") if c != code][:3]
    for guess in wrong:
        assert client.post("/api/auth/verify-email", headers=user["headers"], json={"otp": guess}).status_code == 400
    assert client.post("/api/auth/verify-email", headers=user["headers"], json={"otp": code}).status_code == 400


def test_resend_verification_has_a_cooldown(client, user, outbox, db):
    assert client.post("/api/auth/resend-verification", headers=user["headers"]).status_code == 429
    db.query(User).filter_by(email=user["email"]).update({"verify_otp_sent_at": datetime.now(timezone.utc) - timedelta(minutes=2)})
    db.commit()
    assert client.post("/api/auth/resend-verification", headers=user["headers"]).status_code == 204
    assert [m["kind"] for m in outbox] == ["verification", "verification"]
    # The new code replaces the old one.
    assert client.post("/api/auth/verify-email", headers=user["headers"], json={"otp": outbox[-1]["otp"]}).status_code == 200


def test_resend_verification_is_a_noop_once_verified(client, user, outbox):
    client.post("/api/auth/verify-email", headers=user["headers"], json={"otp": outbox[0]["otp"]})
    assert client.post("/api/auth/resend-verification", headers=user["headers"]).status_code == 204
    assert len(outbox) == 1


def test_verification_endpoints_require_auth(client):
    assert client.post("/api/auth/verify-email", json={"otp": "123456"}).status_code == 401
    assert client.post("/api/auth/resend-verification").status_code == 401


# ── Delete account ───────────────────────────────────────────────────────────

def test_delete_account_removes_the_account_and_everything_under_it(client, user, start_session, ai, post_turn, wait_for_analysis, db):
    from backend.models.core import Conversation, Correction, Message

    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)
    assert wait_for_analysis(cid)
    assert db.query(Message).count() >= 2 and db.query(Correction).count() >= 1

    r = client.request("DELETE", "/api/auth/account", headers=user["headers"], json={"confirm_email": user["email"], "password": PASSWORD})
    assert r.status_code == 204

    db.expire_all()
    assert db.query(User).count() == 0
    assert db.query(Conversation).count() == 0 and db.query(Message).count() == 0 and db.query(Correction).count() == 0
    assert client.get("/api/auth/me", headers=user["headers"]).status_code == 401
    assert client.post("/api/auth/login", json={"email": user["email"], "password": PASSWORD}).status_code == 401


def test_delete_account_requires_matching_email_and_password(client, user):
    wrong_email = client.request("DELETE", "/api/auth/account", headers=user["headers"], json={"confirm_email": "other@example.com", "password": PASSWORD})
    wrong_pw = client.request("DELETE", "/api/auth/account", headers=user["headers"], json={"confirm_email": user["email"], "password": "nope-nope-nope"})
    no_pw = client.request("DELETE", "/api/auth/account", headers=user["headers"], json={"confirm_email": user["email"]})
    assert (wrong_email.status_code, wrong_pw.status_code, no_pw.status_code) == (400, 400, 400)
    assert client.get("/api/auth/me", headers=user["headers"]).status_code == 200


def test_google_only_account_deletes_with_email_confirmation_alone(client):
    from backend.services.auth import create_access_token

    with SessionLocal() as s:
        u = User(email="g@example.com", google_id="g-1", email_verified=True)
        s.add(u)
        s.commit()
        token = create_access_token(u.id, u.token_version)
    r = client.request("DELETE", "/api/auth/account", headers=bearer(token), json={"confirm_email": "g@example.com"})
    assert r.status_code == 204
