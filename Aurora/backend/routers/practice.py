"""
Practice guidance endpoints.

GET /api/practice/today       — what to practise today: the learner's top live weakness
GET /api/practice/weaknesses  — their weakness profile (what they keep getting wrong, and the trend)
GET /api/practice/difficulty  — how demanding the next session will be, and why
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.core import User
from backend.services import difficulty, weaknesses

router = APIRouter(prefix="/api/practice", tags=["practice"])

# Shown to someone with no mistake history yet.
_STARTER = {
    "label": "Get to know your coach",
    "focus": None,
    "why": "Finish a few sessions and AURA will start suggesting what to work on.",
    "suggested_scenario": "casual",
}


@router.get("/today")
def practice_today(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Today's exercise. `focus` is what to pass to POST /api/conversation/start so the
    coach steers the chat toward that weakness; `suggested_scenario` is where it comes
    up most naturally.
    """
    exercise = weaknesses.today_exercise(weaknesses.get_profile(db, user.id))
    return {"has_focus": exercise is not None, "exercise": exercise or _STARTER}


@router.get("/weaknesses")
def practice_weaknesses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = weaknesses.get_profile(db, user.id)
    return {"weaknesses": [weaknesses.weakness_to_dict(w) for w in profile[:10]]}


@router.get("/difficulty")
def practice_difficulty(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    The level the next session will run at: the learner's pinned one, else the one their
    recent scores call for (`auto_tier`, which differs from `tier` only when they've pinned).
    `trend` is the effect of their last scored session on the automatic level.
    """
    return difficulty.current(db, user)
