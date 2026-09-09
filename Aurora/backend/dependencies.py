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
from backend.services.auth import decode_access_token

# auto_error=False so a missing header produces our own 401 with a consistent
# body, rather than FastAPI's default 403 for absent credentials.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolves the caller from their Bearer token.

    Raises 401 for a missing, malformed, expired, or tampered token, or when
    the token is validly signed but its user no longer exists (e.g. deleted
    account with a still-unexpired token).
    """
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _UNAUTHORIZED

    user = db.query(User).filter_by(id=user_id).first()
    if user is None:
        raise _UNAUTHORIZED

    return user
