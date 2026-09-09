"""
Authentication endpoints.

POST /api/auth/signup — create an account, returns a JWT
POST /api/auth/login  — exchange credentials for a JWT
GET  /api/auth/me     — current user from the Bearer token
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.core import User
from backend.schemas.core import AuthUser, LoginRequest, SignupRequest, TokenResponse
from backend.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Deliberately identical for "no such email" and "wrong password" — telling
# them apart lets an attacker enumerate which emails have accounts.
_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid email or password",
)


def _normalize_email(email: str) -> str:
    """Emails are case-insensitive in practice; store and compare lowercased."""
    return email.strip().lower()


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """Creates an account and returns a token, so signup logs you straight in."""
    email = _normalize_email(payload.email)

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        )

    user = User(
        email=email,
        display_name=(payload.display_name or "").strip() or None,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        user=AuthUser.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    user = db.query(User).filter(User.email == email).first()

    # verify_password() returns False on a NULL hash (legacy anonymous rows),
    # so those accounts correctly fail login rather than erroring.
    if user is None or not verify_password(payload.password, user.password_hash or ""):
        raise _INVALID_CREDENTIALS

    return TokenResponse(
        access_token=create_access_token(user.id),
        user=AuthUser.model_validate(user),
    )


@router.get("/me", response_model=AuthUser)
def me(user: User = Depends(get_current_user)):
    return user
