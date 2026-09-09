"""
Authentication service — password hashing and JWT issue/verify.

Uses the `bcrypt` library directly rather than passlib: passlib has been
unmaintained since 2020 and its bcrypt backend detection is broken against
bcrypt 5.x (it probes with an over-length password, which modern bcrypt
rejects instead of silently truncating).
"""
import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from backend.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET


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
