"""
Config options endpoint.
GET /api/config/options — voice/style/scenario picker data for the frontend.

Sourced directly from backend/personalities.py so the frontend never
hand-duplicates this data and can't drift from what the backend actually
supports.
"""
from fastapi import APIRouter

from backend.personalities import (
    DEFAULT_SCENARIO,
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    SCENARIOS,
    STYLES,
    VOICES,
)

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/options")
def get_options():
    """Returns voice/style/scenario choices for session setup, plus defaults."""
    return {
        "voices": [
            {"id": vid, "label": v["label"], "desc": v["desc"], "gender": v["gender"]}
            for vid, v in VOICES.items()
        ],
        "styles": [
            {"id": sid, "label": s["label"]}
            for sid, s in STYLES.items()
        ],
        "scenarios": [
            {"id": scid, "label": sc["label"]}
            for scid, sc in SCENARIOS.items()
        ],
        "defaults": {
            "voice": DEFAULT_VOICE,
            "style": DEFAULT_STYLE,
            "scenario": DEFAULT_SCENARIO,
        },
    }
