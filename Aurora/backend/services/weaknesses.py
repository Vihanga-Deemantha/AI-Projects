"""
Weakness profiling: which kinds of mistake does this learner keep making, and
are they getting better?

Everything is derived from the `corrections` table, so the `user_weaknesses`
rows are a cache that can be dropped and rebuilt at any time. The pure maths
(`compute`) is separate from the database code so it is unit-tested directly.

The one subtle point is the trend. Counting mistakes per month punishes people
for practising MORE (twice the sessions, twice the mistakes, "worsening!"), so
the trend compares mistakes PER SESSION in the last 30 days against the 30 days
before that.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import taxonomy
from backend.models.core import Conversation, Correction, Message
from backend.models.reports import UserWeakness

RECENT = timedelta(days=30)
IMPROVING_BELOW = 0.6       # recent rate under 60% of the earlier rate = improving
WORSENING_ABOVE = 1.4       # ...over 140% = worsening
MIN_COUNT_FOR_TREND = 2     # fewer mistakes than this in the relevant window is too little to call
RECENT_WEIGHT = 3           # a recent mistake counts three times as much as an old one when ranking
CACHE_MAX_AGE = timedelta(hours=1)


@dataclass
class Mistake:
    category: str
    subtype: str
    when: datetime
    conversation_id: str


@dataclass
class Weakness:
    category: str
    subtype: str
    occurrence_count: int
    recent_count: int
    previous_count: int
    sessions_seen: int
    priority: float
    trend: str                  # new | improving | stable | worsening
    first_seen_at: datetime
    last_seen_at: datetime


def _trend(recent: int, previous: int, recent_sessions: int, previous_sessions: int, first_seen: datetime, now: datetime) -> str:
    if previous == 0:
        return "new" if recent > 0 and now - first_seen <= RECENT else "stable"
    if recent_sessions == 0:
        return "stable"           # no recent practice, so no evidence either way
    rate_recent = recent / recent_sessions
    rate_previous = previous / max(previous_sessions, 1)
    if previous >= MIN_COUNT_FOR_TREND and rate_recent <= IMPROVING_BELOW * rate_previous:
        return "improving"
    if recent >= MIN_COUNT_FOR_TREND and rate_recent >= WORSENING_ABOVE * rate_previous:
        return "worsening"
    return "stable"


def compute(mistakes: list[Mistake], session_times: list[datetime], now: datetime) -> list[Weakness]:
    """
    The learner's weaknesses, most important first.

    Args:
        mistakes:      every mistake (not suggestion, not praise) they have made.
        session_times: when each of their finished sessions with speech ended — the
                       denominator for "mistakes per session".
    """
    recent_cut, previous_cut = now - RECENT, now - 2 * RECENT
    recent_sessions = sum(1 for t in session_times if t > recent_cut)
    previous_sessions = sum(1 for t in session_times if previous_cut < t <= recent_cut)

    groups: dict[tuple[str, str], list[Mistake]] = {}
    for m in mistakes:
        groups.setdefault((m.category, m.subtype), []).append(m)

    out = []
    for (category, subtype), items in groups.items():
        recent = sum(1 for m in items if m.when > recent_cut)
        previous = sum(1 for m in items if previous_cut < m.when <= recent_cut)
        first_seen = min(m.when for m in items)
        out.append(Weakness(
            category=category, subtype=subtype,
            occurrence_count=len(items), recent_count=recent, previous_count=previous,
            sessions_seen=len({m.conversation_id for m in items}),
            priority=float(RECENT_WEIGHT * recent + (len(items) - recent)),
            trend=_trend(recent, previous, recent_sessions, previous_sessions, first_seen, now),
            first_seen_at=first_seen, last_seen_at=max(m.when for m in items),
        ))
    out.sort(key=lambda w: (-w.priority, -w.last_seen_at.timestamp(), w.subtype))
    return out


# ── Database ──────────────────────────────────────────────────────────────────

def load_mistakes(db: Session, user_id: str) -> list[Mistake]:
    rows = db.execute(
        select(Correction.category, Correction.subtype, Correction.created_at, Correction.conversation_id)
        .where(Correction.user_id == user_id, Correction.is_error.is_(True), Correction.is_positive.is_(False))
    ).all()
    return [Mistake(category=r[0], subtype=r[1], when=r[2], conversation_id=r[3]) for r in rows]


def load_session_times(db: Session, user_id: str) -> list[datetime]:
    rows = db.execute(
        select(Conversation.ended_at, Conversation.started_at)
        .where(
            Conversation.user_id == user_id,
            Conversation.is_complete.is_(True),
            select(Message.id).where(Message.conversation_id == Conversation.id, Message.role == "user").exists(),
        )
    ).all()
    return [ended or started for ended, started in rows]


def recompute(db: Session, user_id: str, now: datetime | None = None) -> list[UserWeakness]:
    """Rebuilds the user's weakness rows from their corrections (idempotent)."""
    now = now or datetime.now(timezone.utc)
    weaknesses = compute(load_mistakes(db, user_id), load_session_times(db, user_id), now)

    def write() -> list[UserWeakness]:
        db.query(UserWeakness).filter(UserWeakness.user_id == user_id).delete()
        rows = [
            UserWeakness(
                user_id=user_id, category=w.category, subtype=w.subtype, occurrence_count=w.occurrence_count,
                recent_count=w.recent_count, previous_count=w.previous_count, sessions_seen=w.sessions_seen,
                priority=w.priority, trend=w.trend, first_seen_at=w.first_seen_at, last_seen_at=w.last_seen_at,
                updated_at=now,
            )
            for w in weaknesses
        ]
        db.add_all(rows)
        db.commit()
        return rows

    try:
        return write()
    except IntegrityError:
        # Two recomputes raced (e.g. two reports finishing together); both compute the
        # same answer, so just redo it on the other's committed state.
        db.rollback()
        return write()


def get_profile(db: Session, user_id: str, now: datetime | None = None) -> list[UserWeakness]:
    """
    The stored profile, rebuilt if it's missing or stale. Staleness matters because
    the 30-day windows move even when nothing new happens (an old mistake ages out
    of "recent" by itself).
    """
    now = now or datetime.now(timezone.utc)
    rows = db.query(UserWeakness).filter(UserWeakness.user_id == user_id).all()
    if not rows:
        if load_mistakes(db, user_id):
            return recompute(db, user_id, now)
        return []
    if now - min(r.updated_at for r in rows) > CACHE_MAX_AGE:
        return recompute(db, user_id, now)
    return sorted(rows, key=lambda r: (-r.priority, -r.last_seen_at.timestamp(), r.subtype))


# ── What the API says ─────────────────────────────────────────────────────────

def weakness_to_dict(w: UserWeakness) -> dict:
    return {
        "category": w.category,
        "subtype": w.subtype,
        "label": taxonomy.label_for(w.category, w.subtype),
        "focus": taxonomy.focus_id(w.category, w.subtype),
        "occurrences": w.occurrence_count,
        "recent": w.recent_count,
        "previous": w.previous_count,
        "sessions": w.sessions_seen,
        "trend": w.trend,
        "suggested_scenario": taxonomy.scenario_for(w.subtype),
        "last_seen_at": w.last_seen_at.isoformat(),
    }


def _actionable(profile: list[UserWeakness]) -> list[UserWeakness]:
    """Weaknesses worth building an exercise around: not the catch-all 'other' bucket."""
    return [w for w in profile if w.subtype != "other"]


def today_exercise(profile: list[UserWeakness]) -> dict | None:
    """
    Today's practice: the top weakness that is still a live problem. A weakness that
    hasn't appeared in 30 days is already fixed in practice, so recent ones come first;
    only if nothing is recent do we fall back to the all-time top.
    """
    candidates = _actionable(profile)
    live = [w for w in candidates if w.recent_count > 0]
    chosen = (live or candidates or [None])[0]
    if chosen is None:
        return None

    label = taxonomy.label_for(chosen.category, chosen.subtype)
    if chosen.recent_count > 0:
        n = chosen.recent_count
        why = f"{n} {label.lower()} {'mistake' if n == 1 else 'mistakes'} in the last 30 days"
        if chosen.trend == "improving":
            why += " — and improving. Keep it up."
        elif chosen.trend == "worsening":
            why += " — it's been slipping lately."
    else:
        why = f"A recurring one for you ({chosen.occurrence_count} so far). Worth a refresher."
    return {
        "category": chosen.category,
        "subtype": chosen.subtype,
        "label": label,
        "focus": taxonomy.focus_id(chosen.category, chosen.subtype),
        "why": why,
        "trend": chosen.trend,
        "suggested_scenario": taxonomy.scenario_for(chosen.subtype),
    }
