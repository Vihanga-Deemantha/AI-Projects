"""
Google OAuth endpoints.

GET  /api/auth/google              — redirect the browser to Google's consent screen
GET  /api/auth/google/callback     — Google redirects back here with a code
POST /api/auth/google/link-code    — (signed in) mint a short-lived code that starts a "connect Google" flow
POST /api/auth/google/exchange     — trade the one-time code from the callback redirect for a session
POST /api/auth/google/disconnect   — unlink Google from the current account

All of these live under the same /api/auth prefix as routers/auth.py but stay
in their own module since the OAuth flow (state cookie, redirects, account
linking) is a distinct chunk of logic from password auth.

Why codes instead of tokens in URLs: a top-level browser redirect can't carry an
Authorization header, and anything in a URL ends up in browser history, server
logs and referrers. So a long-lived session JWT never goes in a URL. Instead:

  * Sign in: the callback redirects to the frontend with a 2-minute, single-use
    `code`; the frontend POSTs it to /google/exchange and receives the session.
  * Connect (already signed in): the frontend first POSTs /google/link-code to
    get a 5-minute code that names the account, and passes THAT in the URL.
    Its user id is folded into the CSRF `state` (as "<csrf>:<user_id>"); the
    callback re-derives the intent from the same state value it already has to
    validate against the cookie, so a forged state can't claim to be a link for
    an arbitrary account.
"""
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.config import COOKIE_SECURE, FRONTEND_URL
from backend.database import SessionLocal, get_db
from backend.dependencies import get_current_user
from backend.models.core import User
from backend.schemas.core import AuthUser, GoogleExchangeRequest, TokenResponse
from backend.services.auth import create_access_token, create_purpose_token, decode_purpose_token
from backend.services.google_oauth import (
    GoogleOAuthError,
    GoogleOAuthNotConfiguredError,
    exchange_code,
    get_authorization_url,
    get_google_user,
)
from backend.services.ratelimit import client_ip, enforce

router = APIRouter(prefix="/api/auth", tags=["auth"])

STATE_COOKIE = "aura_oauth_state"
LINK_PURPOSE = "google_link"
EXCHANGE_PURPOSE = "google_exchange"
LINK_CODE_TTL_SECONDS = 5 * 60
EXCHANGE_CODE_TTL_SECONDS = 2 * 60
EXCHANGE_PER_IP = (30, 15 * 60)


@router.get("/google")
def google_login(link_code: str | None = None):
    """
    Redirects to Google's consent screen, with a CSRF state token in a
    short-lived cookie. If `link_code` is valid, this is a "connect Google to my
    account" request rather than a login.
    """
    link_user_id = None
    if link_code is not None:
        link_user_id = decode_purpose_token(link_code, LINK_PURPOSE)
        if not link_user_id:
            # The link code expired (or was tampered with) right as they
            # clicked Connect — fail immediately rather than silently falling
            # through to a plain login, which could land them on the wrong account.
            return RedirectResponse(f"{FRONTEND_URL}/profile?error=google_failed")

    csrf = secrets.token_urlsafe(24)
    state = f"{csrf}:{link_user_id}" if link_user_id else csrf

    try:
        auth_url = get_authorization_url(state)
    except GoogleOAuthNotConfiguredError:
        target = "/profile" if link_user_id else "/login"
        return RedirectResponse(f"{FRONTEND_URL}{target}?error=google_not_configured")

    response = RedirectResponse(auth_url)
    response.set_cookie(
        STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax", secure=COOKIE_SECURE
    )
    return response


@router.post("/google/link-code")
def google_link_code(user: User = Depends(get_current_user)):
    """A short-lived code naming the signed-in account, to start a "connect Google" flow."""
    return {"link_code": create_purpose_token(LINK_PURPOSE, user.id, LINK_CODE_TTL_SECONDS)}


@router.get("/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None):
    cookie_state = request.cookies.get(STATE_COOKIE)

    # Missing code, or a state mismatch (forged/replayed/expired callback) —
    # bail out to the same generic error rather than distinguishing why. We
    # can't yet trust `state`'s content to know link-vs-login at this point.
    if not code or not state or not cookie_state or not secrets.compare_digest(state, cookie_state):
        return _fail("google_failed")

    _csrf, _, link_user_id = state.partition(":")
    is_link = bool(link_user_id)

    try:
        access_token = exchange_code(code)
        google_user = get_google_user(access_token)
    except (GoogleOAuthNotConfiguredError, GoogleOAuthError):
        return _fail("google_failed", link=is_link)

    google_id = google_user.get("google_id")
    email = (google_user.get("email") or "").strip().lower()
    if not google_id or not email or not google_user.get("email_verified"):
        return _fail("google_failed", link=is_link)

    with SessionLocal() as db:
        if is_link:
            user = db.get(User, link_user_id)
            if not user:
                return _fail("google_failed")

            conflict = db.query(User).filter(User.google_id == google_id).first()
            if conflict and conflict.id != user.id:
                return _fail("google_link_conflict", link=True)
            if email != (user.email or "").strip().lower():
                return _fail("google_link_mismatch", link=True)

            user.google_id = google_id
            user.email_verified = True  # Google just vouched for this exact address
            if not user.avatar_url and google_user.get("picture"):
                user.avatar_url = google_user["picture"]
            db.commit()
            # They're already signed in: just send them back to their profile,
            # which re-reads the account (now showing Google as connected).
            response = RedirectResponse(f"{FRONTEND_URL}/profile")
        else:
            user = _find_or_create_user(db, google_id, email, google_user)
            exchange = create_purpose_token(EXCHANGE_PURPOSE, user.id, EXCHANGE_CODE_TTL_SECONDS)
            response = RedirectResponse(
                f"{FRONTEND_URL}/auth/google/callback?code={quote(exchange)}&next={quote('/practice')}"
            )

    response.delete_cookie(STATE_COOKIE)
    return response


@router.post("/google/exchange", response_model=TokenResponse)
def google_exchange(payload: GoogleExchangeRequest, request: Request, db: Session = Depends(get_db)):
    """Trades the single-use code from the callback redirect for a real session."""
    enforce("gexchange:ip", client_ip(request), EXCHANGE_PER_IP)
    user_id = decode_purpose_token(payload.code, EXCHANGE_PURPOSE, single_use=True)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=400, detail="That sign-in link has expired. Please try again.")
    return TokenResponse(
        access_token=create_access_token(user.id, user.token_version),
        user=AuthUser.model_validate(user),
    )


@router.post("/google/disconnect", response_model=AuthUser)
def disconnect_google(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Unlinks Google from the current account. Refused for Google-only accounts
    (has_password == False) — disconnecting would leave no way to log back
    in, so the frontend must have the user set a password first.
    """
    if not user.google_linked:
        raise HTTPException(status_code=400, detail="No Google account is linked")
    if not user.has_password:
        raise HTTPException(status_code=400, detail="Set a password before disconnecting Google")

    user.google_id = None
    db.commit()
    db.refresh(user)
    return user


def _find_or_create_user(db: Session, google_id: str, email: str, google_user: dict) -> User:
    """
    Account linking, in priority order:
    1. Existing Google account (by google_id) — log in directly.
    2. Existing password account with the same email — link Google to it.
    3. No match — create a new account from the Google profile.

    Case 2 has a trap. Signup doesn't prove ownership of the email, so an
    attacker can register `victim@example.com` with a password they know and
    wait. If the victim later signs in with Google and we simply linked, the
    attacker's password would still open the account the victim now trusts. So
    when the existing account's email was never verified, Google (which HAS
    verified it) takes the account over: the password is discarded, pending
    codes are cleared, and every existing session is revoked.
    """
    user = db.query(User).filter(User.google_id == google_id).first()
    if user:
        return user

    user = db.query(User).filter(User.email == email).first()
    if user:
        if not user.email_verified:
            user.password_hash = None
            user.reset_otp_hash = None
            user.reset_otp_expires_at = None
            user.reset_otp_attempts = 0
            user.verify_otp_hash = None
            user.verify_otp_expires_at = None
            user.verify_otp_attempts = 0
            user.token_version += 1
        user.google_id = google_id
        user.email_verified = True
        if not user.avatar_url and google_user.get("picture"):
            user.avatar_url = google_user["picture"]
        db.commit()
        db.refresh(user)
        return user

    user = User(
        email=email,
        display_name=google_user.get("name"),
        avatar_url=google_user.get("picture"),
        google_id=google_id,
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _fail(error_code: str, link: bool = False) -> RedirectResponse:
    target = "/profile" if link else "/login"
    response = RedirectResponse(f"{FRONTEND_URL}{target}?error={error_code}")
    response.delete_cookie(STATE_COOKIE)
    return response
