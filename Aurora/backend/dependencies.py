"""
Shared FastAPI dependencies.

get_current_user is the single gate for every authenticated route — routes
should depend on it rather than parsing the Authorization header themselves,
so identity always comes from a verified token and never from client-supplied
request data.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.core import User
from backend.services.auth import decode_access_token_claims

# auto_error=False so a missing header produces our own 401 with a consistent
# body, rather than FastAPI's default 403 for absent credentials.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def user_from_token(db: Session, token: str) -> User | None:
    """
    Resolves a session JWT to its user, or None. Beyond a valid signature and
    expiry, the token's version must match the account's current
    token_version — so changing/resetting a password (which bumps it) logs out
    every other session immediately.
    """
    claims = decode_access_token_claims(token)
    if claims is None:
        return None
    user_id, version = claims
    user = db.get(User, user_id)
    if user is None or user.token_version != version:
        return None
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolves the caller from their Bearer token.

    Raises 401 for a missing, malformed, expired, tampered or revoked token, or
    when the token is validly signed but its user no longer exists (e.g. a
    deleted account with a still-unexpired token).
    """
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED

    user = user_from_token(db, credentials.credentials)
    if user is None:
        raise _UNAUTHORIZED

    return user
