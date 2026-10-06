"""
Adaptive difficulty: how demanding the coach's questions are (tiers 1-5, defined
in personalities.DIFFICULTY_LEVELS).

Where a learner SHOULD be follows their recent performance: the average overall
score of their last three scored sessions maps to a tier (THRESHOLDS). But the tier
only moves ONE step per scored session, so a single great or terrible session never
swings the level by several tiers and makes the next conversation feel jarring.
A learner who prefers a fixed level pins one on their profile, which always wins.

The automatic tier is DERIVED by replaying the learner's report history from the
default tier (`tier_history`), not stored and nudged. That keeps it deterministic,
immune to abandoned sessions (starting a session moves nothing; finishing a scored
one does) and impossible to drift out of step with the reports it comes from.

The maths is pure and unit-tested; the two database helpers just gather the input.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.core import Conversation, User
from backend.models.reports import SessionReport
from backend.personalities import DEFAULT_DIFFICULTY, DIFFICULTY_LEVELS

HISTORY = 3                       # how many recent sessions the average is taken over
# (minimum average score, tier) from the top down; anything below the last is tier 1.
THRESHOLDS = ((90, 5), (78, 4), (65, 3), (50, 2))
MIN_TIER, MAX_TIER = min(DIFFICULTY_LEVELS), max(DIFFICULTY_LEVELS)


def tier_for_scores(scores: list[int]) -> int:
    """Where an average of `scores` says the learner belongs (the default tier with no scores)."""
    if not scores:
        return DEFAULT_DIFFICULTY
    average = sum(scores) / len(scores)
    for minimum, tier in THRESHOLDS:
        if average >= minimum:
            return tier
    return MIN_TIER


def step_toward(tier: int, target: int) -> int:
    """One tier closer to `target` (or `tier` itself if already there) — never more."""
    if target > tier:
        return min(tier + 1, MAX_TIER)
    if target < tier:
        return max(tier - 1, MIN_TIER)
    return tier


def tier_history(scores: list[int]) -> list[int]:
    """
    The tier the learner is on after each scored session.

    `scores` are overall scores, OLDEST first. Starts at the default tier; after each
    session the tier takes one step toward what the average of the last HISTORY scores
    (that session included) says. Returns one tier per score.
    """
    tiers = []
    tier = DEFAULT_DIFFICULTY
    for i in range(len(scores)):
        window = scores[max(0, i - HISTORY + 1): i + 1]
        tier = step_toward(tier, tier_for_scores(window))
        tiers.append(tier)
    return tiers


def trend(before: int, after: int) -> str:
    """'up', 'down' or 'same' — shown as an arrow next to the level."""
    if after == before:
        return "same"
    return "up" if after > before else "down"


# ── Database ──────────────────────────────────────────────────────────────────

def scored_sessions(db: Session, user_id: str) -> list[int]:
    """
    Overall scores of every reported session that has one, OLDEST first. Ordered by when
    the session ended, not when its report was written: reports for old sessions are
    back-filled later, and must not be mistaken for recent performance.
    """
    return list(db.execute(
        select(SessionReport.overall_score)
        .join(Conversation, Conversation.id == SessionReport.conversation_id)
        .where(SessionReport.user_id == user_id, SessionReport.overall_score.is_not(None))
        .order_by(Conversation.ended_at.asc().nulls_last(), SessionReport.generated_at.asc())
    ).scalars().all())


def current(db: Session, user: User) -> dict:
    """
    The difficulty the learner's NEXT session will use, and why — what the UI shows
    ("Difficulty: Intermediate ↑") and what POST /conversation/start applies.
    """
    scores = scored_sessions(db, user.id)
    tiers = tier_history(scores)
    auto = tiers[-1] if tiers else DEFAULT_DIFFICULTY
    before = tiers[-2] if len(tiers) > 1 else DEFAULT_DIFFICULTY
    manual = user.difficulty_override if user.difficulty_override in DIFFICULTY_LEVELS else None
    tier = manual or auto

    recent = scores[-HISTORY:][::-1]       # newest first
    if manual:
        reason = "You chose this level."
    elif not recent:
        reason = "Starting at a comfortable level. It adapts as you practise."
    else:
        shown = ", ".join(str(s) for s in recent)
        reason = f"Based on your last {'session score' if len(recent) == 1 else f'{len(recent)} session scores'}: {shown}."

    return {
        "mode": "manual" if manual else "auto",
        "tier": tier,
        "label": DIFFICULTY_LEVELS[tier]["label"],
        "example": DIFFICULTY_LEVELS[tier]["example"],
        "auto_tier": auto,
        "auto_label": DIFFICULTY_LEVELS[auto]["label"],
        "trend": "same" if manual or not scores else trend(before, auto),
        "reason": reason,
        "recent_scores": recent,
    }
