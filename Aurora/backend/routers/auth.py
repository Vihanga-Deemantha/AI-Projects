"""
Authentication endpoints.

POST /api/auth/signup — create an account, returns a JWT
POST /api/auth/login  — exchange credentials for a JWT
GET  /api/auth/me     — current user from the Bearer token
"""
import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.core import User
from backend.schemas.core import (
    AuthUser,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UpdateProfileRequest,
    VerifyOTPRequest,
)
from backend.services.auth import (
    EmailNotConfiguredError,
    create_access_token,
    generate_otp,
    hash_otp,
    hash_password,
    send_reset_email,
    verify_otp,
    verify_password,
)
from backend.services.upload import AvatarUploadError, upload_avatar

OTP_EXPIRE_MINUTES = 15
OTP_MAX_ATTEMPTS = 3

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


# ── Profile ──────────────────────────────────────────────────────────────────

@router.patch("/profile", response_model=AuthUser)
def update_profile(
    payload: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip() or None
    if payload.bio is not None:
        user.bio = payload.bio.strip() or None
    db.commit()
    db.refresh(user)
    return user


@router.post("/avatar")
async def upload_avatar_endpoint(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validates and uploads to Cloudinary, then stores the CDN URL on the user."""
    contents = await file.read()
    try:
        # upload_avatar() is a blocking network call (services/upload.py) —
        # run it off the event loop, same pattern as STT/LLM/TTS in
        # routers/conversation.py.
        avatar_url = await asyncio.to_thread(
            upload_avatar, contents, file.content_type or "", user.id
        )
    except AvatarUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user.avatar_url = avatar_url
    db.commit()
    return {"avatar_url": avatar_url}


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.has_password:
        if not payload.current_password or not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
    # Google-only accounts (has_password == False) skip the current-password
    # check entirely — there's nothing to verify against yet.

    user.password_hash = hash_password(payload.new_password)
    db.commit()


# ── Forgot password (OTP) ───────────────────────────────────────────────────

_GENERIC_OTP_MESSAGE = "If that email is registered, a 6-digit code is on its way."


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Always 204, whether or not the email exists — telling them apart would let
    an attacker enumerate registered emails. The actual send happens in a
    background task so this returns immediately either way.
    """
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if user:
        otp = generate_otp()
        user.reset_otp_hash = hash_otp(otp)
        user.reset_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
        user.reset_otp_attempts = 0
        db.commit()
        background_tasks.add_task(_send_reset_email_safely, email, otp)


def _send_reset_email_safely(email: str, otp: str):
    """Runs in the background — errors are logged, never surfaced to the caller."""
    try:
        send_reset_email(email, otp)
    except EmailNotConfiguredError:
        print(f"[auth] Password reset requested for {email} but RESEND_API_KEY is not set")
    except Exception as e:
        print(f"[auth] Failed to send reset email to {email}: {e}")


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp_endpoint(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    # Same generic failure for "no such user", "no reset pending", "expired",
    # and "wrong code" — specific reasons would help an attacker narrow down
    # which emails have accounts vs. which have a reset in flight.
    invalid = HTTPException(status_code=400, detail="Invalid or expired code")

    if not user or not user.reset_otp_hash or not user.reset_otp_expires_at:
        raise invalid
    if datetime.now(timezone.utc) > user.reset_otp_expires_at:
        _clear_otp(user, db)
        raise invalid
    if user.reset_otp_attempts >= OTP_MAX_ATTEMPTS:
        _clear_otp(user, db)
        raise invalid

    if not verify_otp(payload.otp, user.reset_otp_hash):
        user.reset_otp_attempts += 1
        if user.reset_otp_attempts >= OTP_MAX_ATTEMPTS:
            _clear_otp(user, db)
        else:
            db.commit()
        raise invalid

    # Success: consume the OTP, set the new password, log the user in.
    _clear_otp(user, db, commit=False)
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        user=AuthUser.model_validate(user),
    )


def _clear_otp(user: User, db: Session, commit: bool = True):
    user.reset_otp_hash = None
    user.reset_otp_expires_at = None
    user.reset_otp_attempts = 0
    if commit:
        db.commit()
