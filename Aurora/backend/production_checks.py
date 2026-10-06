"""
Does this deployment look ready for real users? The production checklist, as code, so a
missed setting is a loud line in the startup log instead of a surprise after launch.

`problems()` is pure — it judges the settings it is given — so it is unit-tested; `run()`
feeds it the real configuration. main.py calls `run()` whenever ENVIRONMENT isn't
"development". Nothing here stops the server from starting: the operator decides.

Each finding is (severity, message): "error" means learners are affected or at risk,
"warning" means worth fixing.
"""
import logging
from urllib.parse import urlsplit

logger = logging.getLogger("aura.production")

# Senders that can't (or can only barely) deliver real mail: the built-in default
# is a domain nobody owns, and Resend's shared test sender only reaches your own address.
_DEFAULT_SENDERS = {"", "noreply@aura.app", "onboarding@resend.dev"}
_PLACEHOLDER_WORDS = ("change", "example", "your_", "your-", "secret", "placeholder", "dev_")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _is_local(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host in _LOCAL_HOSTS or host.endswith(".localhost")


def problems(
    *,
    jwt_secret: str,
    frontend_url: str,
    cors_origins: list[str],
    google_client_id: str,
    google_redirect_uri: str,
    resend_api_key: str,
    email_from: str,
    cloudinary_configured: bool,
    rate_limits_enabled: bool,
    sql_echo: bool,
    log_level: str,
    sentry_dsn: str,
) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []

    def error(message: str) -> None:
        found.append(("error", message))

    def warning(message: str) -> None:
        found.append(("warning", message))

    # ── Secrets ───────────────────────────────────────────────────────────────
    if len(jwt_secret) < 32:
        error('JWT_SECRET is shorter than 32 characters, so sessions are easier to forge. Generate one: python -c "import secrets; print(secrets.token_urlsafe(32))"')
    elif any(word in jwt_secret.lower() for word in _PLACEHOLDER_WORDS):
        error("JWT_SECRET looks like a placeholder from an example file. Generate a random one and keep it private.")

    # ── Where the app lives ───────────────────────────────────────────────────
    if _is_local(frontend_url):
        error("FRONTEND_URL still points at localhost: after Google sign-in, learners would be sent to their own computer.")
    elif not frontend_url.startswith("https://"):
        warning("FRONTEND_URL isn't https. Sign-in tokens and speech would cross the network unencrypted.")
    if any(_is_local(origin) for origin in cors_origins):
        warning("CORS_ORIGINS includes a localhost address. Remove it unless you really want local pages to call this API.")
    if google_client_id and not google_redirect_uri.startswith("https://"):
        error("GOOGLE_REDIRECT_URI isn't https, so the sign-in cookie isn't marked Secure and Google will refuse a non-localhost http redirect.")

    # ── Features that silently do nothing without configuration ───────────────
    if not resend_api_key:
        error("RESEND_API_KEY is not set: nobody can verify their email or reset a forgotten password.")
    if email_from.strip().lower() in _DEFAULT_SENDERS:
        warning("EMAIL_FROM is a default or test sender. Resend's test sender only delivers to your own address until you verify a domain and use it here.")
    if not cloudinary_configured:
        warning("Cloudinary isn't configured, so profile photo uploads will fail.")
    if not sentry_dsn:
        warning("SENTRY_DSN isn't set, so errors in production won't be tracked anywhere you'll see them.")

    # ── Safety switches ───────────────────────────────────────────────────────
    if not rate_limits_enabled:
        error("RATE_LIMITS_ENABLED is off: login, signup and the voice endpoint are open to brute force and abuse.")
    if sql_echo:
        warning("SQL_ECHO is on: every database query, including emails and transcripts, is written to the logs.")
    if log_level == "DEBUG":
        warning("LOG_LEVEL is DEBUG: logs are verbose and may contain personal data. Use INFO in production.")

    return found


def current() -> list[tuple[str, str]]:
    """Judges the real configuration (as read by backend.config) without logging anything."""
    from backend import config

    return problems(
        jwt_secret=config.JWT_SECRET,
        frontend_url=config.FRONTEND_URL,
        cors_origins=config.CORS_ORIGINS,
        google_client_id=config.GOOGLE_CLIENT_ID,
        google_redirect_uri=config.GOOGLE_REDIRECT_URI,
        resend_api_key=config.RESEND_API_KEY,
        email_from=config.EMAIL_FROM,
        cloudinary_configured=bool(config.CLOUDINARY_CLOUD_NAME and config.CLOUDINARY_API_KEY and config.CLOUDINARY_API_SECRET),
        rate_limits_enabled=config.RATE_LIMITS_ENABLED,
        sql_echo=config.SQL_ECHO,
        log_level=config.LOG_LEVEL,
        sentry_dsn=config.SENTRY_DSN,
    )


def run() -> list[tuple[str, str]]:
    """Judges the real configuration and logs each finding; returns them (for tests and tooling)."""
    found = current()
    for severity, message in found:
        (logger.error if severity == "error" else logger.warning)("Production check: %s", message)
    if not found:
        logger.info("Production check: no configuration problems found.")
    return found
