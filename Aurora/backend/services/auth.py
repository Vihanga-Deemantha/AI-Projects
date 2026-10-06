"""
Authentication service — password hashing, JWT issue/verify, OTP codes, email.

Uses the `bcrypt` library directly rather than passlib: passlib has been
unmaintained since 2020 and its bcrypt backend detection is broken against
bcrypt 5.x (it probes with an over-length password, which modern bcrypt
rejects instead of silently truncating).
"""
import base64
import hashlib
import logging
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import resend
from jose import JWTError, jwt

from backend.config import (
    BCRYPT_ROUNDS,
    EMAIL_FROM,
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    JWT_SECRET,
    RESEND_API_KEY,
)

logger = logging.getLogger("aura.auth")


def _prehash(password: str) -> bytes:
    """
    SHA-256 + base64 the password before bcrypt.

    bcrypt silently ignores everything past 72 bytes and truncates at the first
    null byte. Pre-hashing to a fixed 44-byte base64 digest removes both
    footguns, so long passphrases stay fully significant instead of collapsing
    to their first 72 bytes. (Same approach Django and passlib's
    bcrypt_sha256 scheme use.)
    """
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    """Returns a salted bcrypt hash, safe to store."""
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Constant-time password check. Returns False rather than raising on a
    malformed/missing stored hash, so callers can treat it as a plain failure.
    """
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# A real bcrypt hash of a throwaway secret, made once at import. Checking a
# password against it costs exactly as much as checking against a real account,
# which is what makes "no such user" indistinguishable from "wrong password".
_DUMMY_HASH: str = hash_password(secrets.token_urlsafe(24))


def verify_password_constant_time(password: str, password_hash: str | None) -> bool:
    """
    Like verify_password(), but a missing hash (no such user, or a Google-only
    account) still burns a full bcrypt check — so response time never reveals
    whether an email is registered or how it signs in.
    """
    if not password_hash:
        verify_password(password, _DUMMY_HASH)
        return False
    return verify_password(password, password_hash)


# ── Session tokens ──────────────────────────────────────────────────────────

def create_access_token(user_id: str, token_version: int = 0) -> str:
    """
    Issues a signed JWT carrying the user id in `sub` and the account's
    token_version in `tv`. Bumping User.token_version later invalidates it.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "tv": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token_claims(token: str) -> tuple[str, int] | None:
    """
    Verifies signature + expiry and returns (user_id, token_version), or None if
    the token is invalid, expired, tampered with, or is a short-lived
    purpose-scoped token (those must never act as a session). Never raises.
    Tokens issued before versioning existed have no `tv` and count as version 0.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    if "purpose" in payload:
        return None
    user_id = payload.get("sub")
    version = payload.get("tv", 0)
    if not isinstance(user_id, str) or not isinstance(version, int):
        return None
    return user_id, version


# ── Short-lived, single-purpose tokens ──────────────────────────────────────
# Used to hand a browser a credential for exactly one step (finish a Google
# sign-in, start a Google link) without putting a long-lived session token in
# a URL, where it would end up in history, logs and referrers.

_used_jtis: dict[str, float] = {}
_used_lock = threading.Lock()


def create_purpose_token(purpose: str, subject: str, ttl_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "purpose": purpose,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_purpose_token(token: str, purpose: str, single_use: bool = False) -> str | None:
    """
    Returns the token's subject if it is valid, unexpired and was issued for
    `purpose`; otherwise None. With single_use=True the token is consumed — a
    second presentation returns None (per-process memory, which matches the
    single-worker deployment; entries expire with the token).
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("purpose") != purpose:
        return None
    subject, jti = payload.get("sub"), payload.get("jti")
    if not isinstance(subject, str) or not isinstance(jti, str):
        return None
    if single_use:
        now = time.time()
        with _used_lock:
            for stale in [k for k, exp in _used_jtis.items() if exp < now]:
                del _used_jtis[stale]
            if jti in _used_jtis:
                return None
            _used_jtis[jti] = float(payload.get("exp", now + 600))
    return subject


# ── One-time codes (password reset, email verification) ─────────────────────
# Same bcrypt-with-prehash approach as passwords above — an OTP is just a
# short-lived, single-purpose password, so it gets the same treatment: never
# stored or logged in the clear, only as a hash.

def generate_otp() -> str:
    """A cryptographically random 6-digit code, zero-padded (e.g. '004821')."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    return bcrypt.hashpw(_prehash(otp), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_otp(otp: str, otp_hash: str) -> bool:
    """Same not-raising-on-malformed-hash contract as verify_password()."""
    if not otp_hash:
        return False
    try:
        return bcrypt.checkpw(_prehash(otp), otp_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verify_otp_constant_time(otp: str, otp_hash: str | None) -> bool:
    """
    verify_otp() that always spends a full bcrypt check, even with no code
    pending — so response time doesn't reveal whether an account has one.
    """
    if not otp_hash:
        verify_otp(otp, _DUMMY_HASH)
        return False
    return verify_otp(otp, otp_hash)


class EmailNotConfiguredError(Exception):
    """Raised when RESEND_API_KEY is unset — callers log it and carry on."""


def _send_code_email(to_email: str, otp: str, subject: str, intro: str) -> None:
    if not RESEND_API_KEY:
        raise EmailNotConfiguredError("RESEND_API_KEY is not configured")

    resend.api_key = RESEND_API_KEY
    resend.Emails.send({
        "from": EMAIL_FROM,
        "to": [to_email],
        "subject": subject,
        "html": f"""
            <div style="font-family:sans-serif;max-width:420px;margin:0 auto;padding:32px 24px;">
              <p style="font-size:14px;color:#555;">{intro} It expires in 15 minutes.</p>
              <p style="font-size:32px;font-weight:700;letter-spacing:6px;
                        text-align:center;margin:28px 0;">{otp}</p>
              <p style="font-size:12px;color:#999;">
                If you didn't request this, you can safely ignore this email.
              </p>
            </div>
        """,
    })


def send_reset_email(to_email: str, otp: str) -> None:
    """Sends the password-reset OTP via Resend. Raises EmailNotConfiguredError if unconfigured."""
    _send_code_email(
        to_email, otp,
        subject=f"Your AURA verification code: {otp}",
        intro="Use this code to reset your AURA password.",
    )


def send_verification_email(to_email: str, otp: str) -> None:
    """Sends the verify-your-email OTP via Resend. Raises EmailNotConfiguredError if unconfigured."""
    _send_code_email(
        to_email, otp,
        subject=f"Confirm your AURA email: {otp}",
        intro="Use this code to confirm your email address and finish setting up AURA.",
    )
