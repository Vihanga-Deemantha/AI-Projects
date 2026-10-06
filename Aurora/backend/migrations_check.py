"""
Is the database at the schema this code expects?

The app no longer calls Base.metadata.create_all() at startup: that only ever
creates MISSING tables and never adds columns, so it quietly hides an
un-applied migration until a query fails at runtime. Instead, startup compares
the database's Alembic revision with the code's latest one and says so clearly.
"""
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

_BACKEND_DIR = Path(__file__).resolve().parent
UPGRADE_COMMAND = "alembic -c backend/alembic.ini upgrade head   (run from the Aurora/ folder)"


def head_revision() -> str | None:
    config = Config(str(_BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def current_revision(engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def check_schema(engine) -> tuple[bool, str]:
    """Returns (is_up_to_date, human-readable message)."""
    head = head_revision()
    current = current_revision(engine)
    if current == head:
        return True, f"Database schema is up to date ({head})."
    if current is None:
        return False, f"Database has no Alembic version (expected {head}). Run: {UPGRADE_COMMAND}"
    return False, f"Database schema is {current}, code expects {head}. Run: {UPGRADE_COMMAND}"
