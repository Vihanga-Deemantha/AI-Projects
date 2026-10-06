"""
Config options endpoint.
GET /api/config/options — voice/style/scenario picker data for the frontend.

Sourced directly from backend/personalities.py so the frontend never
hand-duplicates this data and can't drift from what the backend actually
supports. Voices are filtered to the ones whose model file is installed on this
machine, so the picker can never offer a companion that would fail to speak. Each
companion lists the speaking styles they can actually speak (a style brings an accent,
and not every companion has a voice for every accent), so the picker never offers a
combination the server would refuse.
"""
from fastapi import APIRouter

from backend import taxonomy
from backend.personalities import (
    ACCENT_LABELS,
    DEFAULT_SCENARIO,
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    DIFFICULTY_LEVELS,
    SCENARIOS,
    STYLES,
    VOICES,
)
from backend.services import tts

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/options")
def get_options():
    """Returns voice/style/scenario choices for session setup, plus defaults."""
    voices = [
        {
            "id": vid, "label": v["label"], "desc": v["desc"], "gender": v["gender"],
            "accent": ACCENT_LABELS[v["accent"]],      # the accent of their own voice (what Standard English uses)
            "styles": [sid for sid in STYLES if tts.style_available(vid, sid)],
        }
        for vid, v in VOICES.items()
        if tts.voice_available(vid)
    ]
    speakable = {sid for v in voices for sid in v["styles"]}      # a style nobody can speak isn't offered
    default_voice = DEFAULT_VOICE if any(v["id"] == DEFAULT_VOICE for v in voices) else (
        voices[0]["id"] if voices else DEFAULT_VOICE
    )
    return {
        "voices": voices,
        "styles": [
            {"id": sid, "label": s["label"], "desc": s.get("desc", ""), "accent": ACCENT_LABELS.get(s["accent"])}
            for sid, s in STYLES.items()
            if sid in speakable
        ],
        "scenarios": [
            {"id": scid, "label": sc["label"]}
            for scid, sc in SCENARIOS.items()
        ],
        # What a session can be steered toward (every kind of mistake we track).
        "focus_areas": [
            {"id": taxonomy.focus_id(category, subtype), "label": info["label"], "category": category,
             "scenario": taxonomy.scenario_for(subtype)}
            for category in taxonomy.MISTAKE_SUBTYPES
            for subtype, info in taxonomy.SUBTYPES[category].items()
            if subtype != "other"
        ],
        "difficulties": [
            {"level": level, "label": d["label"], "example": d["example"]}
            for level, d in DIFFICULTY_LEVELS.items()
        ],
        "defaults": {
            "voice": default_voice,
            "style": DEFAULT_STYLE,
            "scenario": DEFAULT_SCENARIO,
        },
    }
