"""
Error tracking (Sentry). Optional: switched on by SENTRY_DSN, a no-op without it.

A learner's words are personal. A stack trace that carries a transcript, a password or a
login token would only move that data to another company, so the SDK is told to send no
personal data, no request bodies and no local variables: it reports WHERE and WHAT broke,
never what the learner said. And error tracking must never be the thing that takes the app
down, so a missing SDK or a bad DSN is logged and the app carries on without it.
"""
import logging

logger = logging.getLogger("aura.observability")


def init_error_tracking(dsn: str, environment: str) -> bool:
    """Starts Sentry if a DSN is configured and the SDK is installed. Returns whether it is now on."""
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk isn't installed (pip install sentry-sdk)")
        return False

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            send_default_pii=False,            # no IP addresses, cookies or auth headers
            max_request_body_size="never",     # request bodies hold passwords, bios and form fields
            include_local_variables=False,     # traceback frames would otherwise carry transcripts
        )
    except Exception:
        logger.exception("Sentry couldn't be started (is SENTRY_DSN correct?); continuing without error tracking")
        return False
    logger.info("Sentry error tracking enabled")
    return True
