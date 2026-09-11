"""
Google OAuth 2.0 — server-side authorization code flow.

Implemented directly against Google's endpoints via httpx (already a
dependency) rather than pulling in google-auth-oauthlib: a confidential-client
authorization-code exchange plus a userinfo fetch is a handful of HTTP calls,
not enough surface to justify another library.
"""
import httpx

from backend.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleOAuthNotConfiguredError(Exception):
    """Raised when GOOGLE_CLIENT_ID/SECRET aren't set — router turns this into a clear 503."""


class GoogleOAuthError(Exception):
    """The exchange or userinfo call failed (bad/expired code, revoked consent, etc.)."""


def _ensure_configured() -> None:
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        raise GoogleOAuthNotConfiguredError("Google sign-in is not configured on this server")


def get_authorization_url(state: str) -> str:
    """Builds the URL to redirect the browser to for the Google consent screen."""
    _ensure_configured()
    params = httpx.QueryParams({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    })
    return f"{AUTH_ENDPOINT}?{params}"


def exchange_code(code: str) -> str:
    """Exchanges an authorization code for an access token. Returns the access token."""
    _ensure_configured()
    try:
        resp = httpx.post(TOKEN_ENDPOINT, data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_REDIRECT_URI,
        }, timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise GoogleOAuthError(f"Token exchange failed: {exc}") from exc

    access_token = resp.json().get("access_token")
    if not access_token:
        raise GoogleOAuthError("Google did not return an access token")
    return access_token


def get_google_user(access_token: str) -> dict:
    """Returns {google_id, email, email_verified, name, picture} for the authenticated Google user."""
    try:
        resp = httpx.get(
            USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise GoogleOAuthError(f"Fetching Google user info failed: {exc}") from exc

    data = resp.json()
    return {
        "google_id": data.get("sub"),
        "email": data.get("email"),
        # Almost always true for consumer Google accounts, but a Workspace
        # domain can federate in an identity provider that leaves this false
        # — don't trust the email for linking/creating an account unless
        # Google itself vouches for it.
        "email_verified": data.get("email_verified", False),
        "name": data.get("name"),
        "picture": data.get("picture"),
    }
