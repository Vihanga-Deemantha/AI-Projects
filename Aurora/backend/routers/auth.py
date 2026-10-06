"""
Authentication endpoints.

POST   /api/auth/signup               — create an account, returns a JWT (sends a verification code)
POST   /api/auth/login                — exchange credentials for a JWT
GET    /api/auth/me                   — current user from the Bearer token
PATCH  /api/auth/profile              — display name / bio / preferences
POST   /api/auth/avatar               — upload a profile photo
POST   /api/auth/change-password      — change/set a password (returns a fresh JWT; other sessions end)
POST   /api/auth/forgot-password      — email a 6-digit reset code
POST   /api/auth/verify-otp           — reset the password with that code
POST   /api/auth/verify-email         — confirm email ownership with the signup code
POST   /api/auth/resend-verification  — send a new signup code
DELETE /api/auth/account              — permanently delete the account and its data

Security posture, in one place:
  * No account enumeration: wrong-password and unknown-email take the same time
    and return the same error; forgot-password always answers 204.
  * Every guessable thing is rate limited (services/ratelimit.py).
  * A password change/reset bumps User.token_version, which logs out every other
    session — including one an attacker may have created.
"""
import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from backend.config import IS_DEVELOPMENT
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.core import User
from backend.personalities import STYLES, VOICES
from backend.schemas.core import (
    AuthUser,
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UpdateProfileRequest,
    VerifyEmailRequest,
    VerifyOTPRequest,
)
from backend.services import auth as auth_service, tts
from backend.services.auth import (
    EmailNotConfiguredError,
    create_access_token,
    generate_otp,
    hash_otp,
    hash_password,
    verify_password,
    verify_password_constant_time,
)
from backend.services.ratelimit import (
    AVATAR_PER_USER,
    ACCOUNT_DELETE_PER_USER,
    EMAIL_CODE_SEND_PER_USER,
    EMAIL_VERIFY_PER_USER,
    FORGOT_PER_EMAIL,
    FORGOT_PER_IP,
    LOGIN_FAIL_PER_EMAIL,
    LOGIN_FAIL_PER_IP_EMAIL,
    LOGIN_PER_IP,
    OTP_VERIFY_PER_EMAIL,
    OTP_VERIFY_PER_IP,
    SIGNUP_PER_IP,
    client_ip,
    enforce,
    limiter,
    too_many,
)
from backend.services.upload import AvatarUploadError, delete_avatar, upload_avatar

logger = logging.getLogger("aura.auth")

OTP_EXPIRE_MINUTES = 15
OTP_MAX_ATTEMPTS = 3
OTP_RESEND_COOLDOWN_SECONDS = 60

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _invalid_credentials() -> HTTPException:
    # Deliberately identical for "no such email" and "wrong password" — telling
    # them apart lets an attacker enumerate which emails have accounts.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )


def _normalize_email(email: str) -> str:
    """Emails are case-insensitive in practice; store and compare lowercased."""
    return email.strip().lower()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.token_version),
        user=AuthUser.model_validate(user),
    )


def _deliver_code(kind: str, email: str, otp: str) -> None:
    """
    Sends a one-time code by email. Runs in the background — errors are logged,
    never surfaced to the caller (that would leak whether the address exists).
    """
    sender = auth_service.send_verification_email if kind == "verification" else auth_service.send_reset_email
    try:
        sender(email, otp)
    except EmailNotConfiguredError:
        if IS_DEVELOPMENT:
            # Dev convenience only: without an email provider the code would
            # otherwise be unreachable. Never done outside development.
            logger.warning("[dev] Email isn't configured, so the %s code for %s is: %s", kind, email, otp)
        else:
            logger.error("A %s code was requested for %s but RESEND_API_KEY is not set", kind, email)
    except Exception:
        logger.exception("Failed to send the %s email", kind)


def _cooldown_remaining(sent_at: datetime | None) -> int:
    """Seconds left before another code may be sent (0 = go ahead)."""
    if sent_at is None:
        return 0
    remaining = OTP_RESEND_COOLDOWN_SECONDS - (_now() - sent_at).total_seconds()
    return max(0, math.ceil(remaining))


def _issue_verification_code(user: User, db: Session, background_tasks: BackgroundTasks) -> None:
    otp = generate_otp()
    user.verify_otp_hash = hash_otp(otp)
    user.verify_otp_expires_at = _now() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    user.verify_otp_attempts = 0
    user.verify_otp_sent_at = _now()
    db.commit()
    background_tasks.add_task(_deliver_code, "verification", user.email, otp)


# ── Signup / login ───────────────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Creates an account and returns a token, so signup logs you straight in."""
    enforce("signup:ip", client_ip(request), SIGNUP_PER_IP)
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
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Prove the address is theirs. Nothing is blocked while unverified, but an
    # unverified address is never trusted (e.g. for auto-linking Google).
    _issue_verification_code(user, db, background_tasks)
    db.refresh(user)

    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    email = _normalize_email(payload.email)

    enforce("login:ip", ip, LOGIN_PER_IP)
    # Failures are counted per (IP, email) so one person can't lock a victim out
    # from their own machine, and per email overall as a backstop against a
    # distributed guess.
    fail_trackers = [
        ("login:fail:ip_email", f"{ip}|{email}", LOGIN_FAIL_PER_IP_EMAIL),
        ("login:fail:email", email, LOGIN_FAIL_PER_EMAIL),
    ]
    for bucket, key, (limit, window) in fail_trackers:
        wait = limiter.retry_after(bucket, key, limit, window)
        if wait:
            raise too_many(wait, "Too many failed sign-in attempts. Please try again later.")

    user = db.query(User).filter(User.email == email).first()

    # Always spends a full bcrypt check — unknown email and Google-only
    # accounts included — so timing never reveals which emails are registered.
    password_ok = verify_password_constant_time(payload.password, user.password_hash if user else None)

    if user is None or not password_ok:
        for bucket, key, (_limit, window) in fail_trackers:
            limiter.record(bucket, key, window)
        raise _invalid_credentials()

    for bucket, key, _policy in fail_trackers:
        limiter.clear(bucket, key)
    return _token_response(user)


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
    if payload.preferred_voice is not None:
        if payload.preferred_voice not in VOICES:
            raise HTTPException(status_code=400, detail="Unknown companion")
        user.preferred_voice = payload.preferred_voice
    if payload.preferred_style is not None:
        if payload.preferred_style not in STYLES:
            raise HTTPException(status_code=400, detail="Unknown speaking style")
        user.preferred_style = payload.preferred_style
    if payload.preferred_voice is not None or payload.preferred_style is not None:
        # the style brings an accent: the saved companion must have a voice for it
        problem = tts.style_problem(user.preferred_voice, user.preferred_style)
        if problem:
            raise HTTPException(status_code=400, detail=problem)
    if "difficulty_override" in payload.model_fields_set:
        user.difficulty_override = payload.difficulty_override   # None = back to automatic
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
    enforce("avatar:user", user.id, AVATAR_PER_USER, "Too many photo uploads. Please try again later.")
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


# ── Password ─────────────────────────────────────────────────────────────────

@router.post("/change-password", response_model=TokenResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sets a new password and ends every other session. Returns a fresh token for
    THIS session so the caller stays signed in.
    """
    if user.has_password:
        # An attacker holding a stolen session could otherwise brute-force the
        # current password through this endpoint.
        wait = limiter.retry_after("pwchange:fail", user.id, 5, 15 * 60)
        if wait:
            raise too_many(wait, "Too many incorrect attempts. Please try again later.")
        if not payload.current_password or not verify_password(payload.current_password, user.password_hash or ""):
            limiter.record("pwchange:fail", user.id, 15 * 60)
            # 400, not 401: the caller IS authenticated. A 401 makes the frontend treat this
            # as an expired session and log the user out.
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        limiter.clear("pwchange:fail", user.id)
    # Google-only accounts (has_password == False) skip the current-password
    # check entirely — there's nothing to verify against yet.

    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    db.commit()
    db.refresh(user)
    return _token_response(user)


# ── Forgot password (OTP) ───────────────────────────────────────────────────

@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Always 204, whether or not the email exists — telling them apart would let
    an attacker enumerate registered emails. That includes timing: the (slow)
    OTP hash is computed up front on every call, and the email send happens in a
    background task.

    Requests inside the resend cooldown, or past the per-email hourly limit, are
    silently ignored. Without that, every request would issue a fresh code and
    reset the 3-attempt counter, handing an attacker unlimited guesses.
    """
    enforce("forgot:ip", client_ip(request), FORGOT_PER_IP)
    email = _normalize_email(payload.email)

    otp = generate_otp()
    otp_hash = hash_otp(otp)  # same cost whether or not the account exists

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return

    within_limit = limiter.check_and_record("forgot:email", email, *FORGOT_PER_EMAIL) == 0
    if not within_limit or _cooldown_remaining(user.reset_otp_sent_at) > 0:
        return

    user.reset_otp_hash = otp_hash
    user.reset_otp_expires_at = _now() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    user.reset_otp_attempts = 0
    user.reset_otp_sent_at = _now()
    db.commit()
    background_tasks.add_task(_deliver_code, "reset", email, otp)


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp_endpoint(payload: VerifyOTPRequest, request: Request, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    enforce("otp:ip", client_ip(request), OTP_VERIFY_PER_IP)
    enforce("otp:email", email, OTP_VERIFY_PER_EMAIL)

    user = db.query(User).filter(User.email == email).first()

    # Same generic failure for "no such user", "no reset pending", "expired",
    # and "wrong code" — specific reasons would help an attacker narrow down
    # which emails have accounts vs. which have a reset in flight.
    invalid = HTTPException(status_code=400, detail="Invalid or expired code")

    pending = bool(user and user.reset_otp_hash and user.reset_otp_expires_at)
    # Always run one bcrypt comparison so timing can't distinguish the cases.
    code_ok = auth_service.verify_otp_constant_time(payload.otp, user.reset_otp_hash if pending else None)

    if not pending:
        raise invalid
    if _now() > user.reset_otp_expires_at:
        _clear_reset_otp(user, db)
        raise invalid
    if user.reset_otp_attempts >= OTP_MAX_ATTEMPTS:
        _clear_reset_otp(user, db)
        raise invalid

    if not code_ok:
        user.reset_otp_attempts += 1
        if user.reset_otp_attempts >= OTP_MAX_ATTEMPTS:
            _clear_reset_otp(user, db)
        else:
            db.commit()
        raise invalid

    # Success: consume the OTP, set the new password, log the user in. Receiving
    # the code proves they control the inbox, so the email counts as verified;
    # bumping the token version ends every older session.
    _clear_reset_otp(user, db, commit=False)
    user.password_hash = hash_password(payload.new_password)
    user.email_verified = True
    user.token_version += 1
    db.commit()
    db.refresh(user)

    return _token_response(user)


def _clear_reset_otp(user: User, db: Session, commit: bool = True):
    user.reset_otp_hash = None
    user.reset_otp_expires_at = None
    user.reset_otp_attempts = 0
    if commit:
        db.commit()


# ── Email verification ───────────────────────────────────────────────────────

@router.post("/verify-email", response_model=AuthUser)
def verify_email(
    payload: VerifyEmailRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirms the signed-in user controls their email address using the emailed code."""
    if user.email_verified:
        return user
    enforce("emailverify:user", user.id, EMAIL_VERIFY_PER_USER, "Too many attempts. Please request a new code later.")

    invalid = HTTPException(status_code=400, detail="Invalid or expired code")
    pending = bool(user.verify_otp_hash and user.verify_otp_expires_at)
    code_ok = auth_service.verify_otp_constant_time(payload.otp, user.verify_otp_hash if pending else None)

    if not pending:
        raise invalid
    if _now() > user.verify_otp_expires_at or user.verify_otp_attempts >= OTP_MAX_ATTEMPTS:
        _clear_verify_otp(user, db)
        raise invalid
    if not code_ok:
        user.verify_otp_attempts += 1
        if user.verify_otp_attempts >= OTP_MAX_ATTEMPTS:
            _clear_verify_otp(user, db)
        else:
            db.commit()
        raise invalid

    user.email_verified = True
    _clear_verify_otp(user, db, commit=False)
    db.commit()
    db.refresh(user)
    return user


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
def resend_verification(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.email_verified or not user.email:
        return
    remaining = _cooldown_remaining(user.verify_otp_sent_at)
    if remaining > 0:
        raise too_many(remaining, f"Please wait {remaining}s before requesting another code.")
    enforce("emailcode:user", user.id, EMAIL_CODE_SEND_PER_USER, "Too many codes requested. Please try again later.")
    _issue_verification_code(user, db, background_tasks)


def _clear_verify_otp(user: User, db: Session, commit: bool = True):
    user.verify_otp_hash = None
    user.verify_otp_expires_at = None
    user.verify_otp_attempts = 0
    if commit:
        db.commit()


# ── Delete account ───────────────────────────────────────────────────────────

@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: DeleteAccountRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permanently deletes the account and everything under it (sessions,
    transcripts, corrections, metrics, reports — all removed by ON DELETE
    CASCADE). Requires the account email typed back, plus the password for
    accounts that have one.
    """
    enforce("acctdelete:user", user.id, ACCOUNT_DELETE_PER_USER)
    if _normalize_email(payload.confirm_email) != (user.email or ""):
        raise HTTPException(status_code=400, detail="That email doesn't match this account.")
    if user.has_password and not verify_password(payload.password or "", user.password_hash or ""):
        raise HTTPException(status_code=400, detail="Password is incorrect")

    had_avatar = bool(user.avatar_url)
    user_id = user.id
    db.delete(user)
    db.commit()
    if had_avatar:
        background_tasks.add_task(delete_avatar, user_id)
