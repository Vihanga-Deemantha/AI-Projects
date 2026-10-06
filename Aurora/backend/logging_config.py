"""
Logging setup. Call configure_logging() once at process start (main.py does).

Application code logs through `logging.getLogger("aura.<area>")` instead of
print(), so LOG_LEVEL actually controls what you see and production logs can be
filtered. SQLAlchemy statement logging is separate and off unless SQL_ECHO=1.
"""
import logging

from backend.config import LOG_LEVEL, SQL_ECHO


def configure_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=LOG_LEVEL,
            format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        )
    else:
        root.setLevel(LOG_LEVEL)

    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if SQL_ECHO else logging.WARNING)

    # HTTP client libraries log every request URL at INFO, and Alembic logs its
    # plugin setup whenever the startup schema check builds a config — pure noise.
    for noisy in ("httpx", "httpcore", "urllib3", "alembic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
