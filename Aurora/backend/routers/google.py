"""
Google OAuth endpoints.

GET  /api/auth/google              — redirect the browser to Google's consent screen
GET  /api/auth/google/callback     — Google redirects back here with a code
POST /api/auth/google/disconnect   — unlink Google from the current account

All three live under the same /api/auth prefix as routers/auth.py but stay in
their own module since the OAuth flow (state cookie, redirects, account
linking) is a distinct chunk of logic from password auth.

Login vs. link: /google is used both for "sign in with Google" (from
/login, no session yet) and "connect Google" (from /profile, already
logged in). A bare redirect can't carry an Authorization header, so the
caller's JWT is passed as `link_token` and folded into the CSRF `state`
(as "<csrf>:<user_id>") after being decoded server-side — never trusted
as a raw client-supplied id. The callback re-derives the intent from the
same state value it already has to validate against the cookie, so a
forged state can't claim to be a link for an arbitrary account.
"""
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.config import FRONTEND_URL
from backend.database import SessionLocal, get_db
from backend.dependencies import get_current_user
from backend.models.core import User
from backend.schemas.core import AuthUser
from backend.services.auth import create_access_token, decode_access_token
from backend.services.google_oauth import (
    GoogleOAuthError,
    GoogleOAuthNotConfiguredError,
    exchange_code,
    get_authorization_url,
    get_google_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

STATE_COOKIE = "aura_oauth_state"


@router.get("/google")
def google_login(link_token: str | None = None):
    """
    Redirects to Google's consent screen, with a CSRF state token in a
    short-lived cookie. If `link_token` is a valid JWT, this is a "connect
    Google to my account" request rather than a login — the target user id
    rides along inside `state` so the callback knows which account to link.
    """
    link_user_id = None
    if link_token is not None:
        link_user_id = decode_access_token(link_token)
        if not link_user_id:
            # Session was invalid/expired right as they clicked Connect —
            # fail immediately rather than silently falling through to a
            # plain login, which could land them on the wrong account.
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
        STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax"
    )
    return response


@router.get("/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None):
    cookie_state = request.cookies.get(STATE_COOKIE)

    # Missing code, or a state mismatch (forged/replayed/expired callback) —
    # bail out to the same generic error rather than distinguishing why. We
    # can't yet trust `state`'s content to know link-vs-login at this point.
    if not code or not state or not cookie_state or state != cookie_state:
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
            if not user.avatar_url and google_user.get("picture"):
                user.avatar_url = google_user["picture"]
            db.commit()
            db.refresh(user)
        else:
            user = _find_or_create_user(db, google_id, email, google_user)

        token = create_access_token(user.id)
        user_json = AuthUser.model_validate(user).model_dump_json()

    next_path = "/profile" if is_link else "/practice"
    response = RedirectResponse(
        f"{FRONTEND_URL}/auth/google/callback?token={quote(token)}&user={quote(user_json)}&next={quote(next_path)}"
    )
    response.delete_cookie(STATE_COOKIE)
    return response


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
    """
    user = db.query(User).filter(User.google_id == google_id).first()
    if user:
        return user

    user = db.query(User).filter(User.email == email).first()
    if user:
        user.google_id = google_id
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
