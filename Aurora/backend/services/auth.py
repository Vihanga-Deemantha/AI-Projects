"""
Authentication service — password hashing and JWT issue/verify.

Uses the `bcrypt` library directly rather than passlib: passlib has been
unmaintained since 2020 and its bcrypt backend detection is broken against
bcrypt 5.x (it probes with an over-length password, which modern bcrypt
rejects instead of silently truncating).
"""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import resend
from jose import JWTError, jwt

from backend.config import (
    EMAIL_FROM,
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    JWT_SECRET,
    RESEND_API_KEY,
)


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
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


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


def create_access_token(user_id: str) -> str:
    """Issues a signed JWT carrying the user id in `sub`."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """
    Verifies signature + expiry. Returns the user id, or None if the token is
    invalid, expired, or tampered with. Never raises — callers turn None into
    a 401.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    user_id = payload.get("sub")
    return user_id if isinstance(user_id, str) else None


# ── Password-reset OTP ──────────────────────────────────────────────────────
# Same bcrypt-with-prehash approach as passwords above — an OTP is just a
# short-lived, single-purpose password, so it gets the same treatment: never
# stored or logged in the clear, only as a hash.

def generate_otp() -> str:
    """A cryptographically random 6-digit code, zero-padded (e.g. '004821')."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    return bcrypt.hashpw(_prehash(otp), bcrypt.gensalt()).decode("utf-8")


def verify_otp(otp: str, otp_hash: str) -> bool:
    """Same not-raising-on-malformed-hash contract as verify_password()."""
    if not otp_hash:
        return False
    try:
        return bcrypt.checkpw(_prehash(otp), otp_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


class EmailNotConfiguredError(Exception):
    """Raised when RESEND_API_KEY is unset — routers turn this into a clear 503."""


def send_reset_email(to_email: str, otp: str) -> None:
    """
    Sends the password-reset OTP via Resend. Raises EmailNotConfiguredError if
    RESEND_API_KEY isn't set, rather than letting the Resend SDK fail with a
    less obvious auth error.
    """
    if not RESEND_API_KEY:
        raise EmailNotConfiguredError("RESEND_API_KEY is not configured")

    resend.api_key = RESEND_API_KEY
    resend.Emails.send({
        "from": EMAIL_FROM,
        "to": [to_email],
        "subject": f"Your AURA verification code: {otp}",
        "html": f"""
            <div style="font-family:sans-serif;max-width:420px;margin:0 auto;padding:32px 24px;">
              <p style="font-size:14px;color:#555;">Use this code to reset your AURA password.
              It expires in 15 minutes.</p>
              <p style="font-size:32px;font-weight:700;letter-spacing:6px;
                        text-align:center;margin:28px 0;">{otp}</p>
              <p style="font-size:12px;color:#999;">
                If you didn't request this, you can safely ignore this email.
              </p>
            </div>
        """,
    })
