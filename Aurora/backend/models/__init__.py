"""Importing this package registers every table on Base.metadata (Alembic and the tests rely on it)."""
from backend.models.core import Conversation, Correction, Message, User  # noqa: F401
from backend.models.metrics import ClarityScore, FluencyEvent, FluencyScore  # noqa: F401
from backend.models.reports import SessionReport, UserWeakness  # noqa: F401
