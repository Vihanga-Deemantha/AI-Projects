"""
Progress over time, computed from a learner's session reports.

Pure functions over a list of `Point`s (one per reported session), so every rule
is unit-tested and nothing here touches the database. The router loads the
points; this module turns them into what the progress page shows: weekly score
trends, a practice streak, totals and a few milestones worth celebrating.

Days and weeks are the LEARNER'S, not the server's: practising at 11:30pm in
Colombo is still "today" there even if it is already tomorrow in UTC. The client
sends its UTC offset and every date calculation applies it.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

DIMENSIONS = ("overall", "grammar", "vocabulary", "fluency", "clarity", "naturalness")

MIN_SESSIONS_FOR_TREND = 4        # fewer sessions than this say nothing about direction
TREND_GROUP = 3                   # compare the earliest N sessions with the latest N
MIN_GAIN_TO_CELEBRATE = 5         # points; smaller changes are noise
STREAK_MILESTONES = (3, 7, 14, 30, 60, 100)
PRACTICE_HOUR_MILESTONES = (1, 5, 10, 25, 50, 100)
SESSION_MILESTONES = (1, 10, 25, 50, 100)
MAX_MILESTONES = 4


@dataclass
class Point:
    conversation_id: str
    when: datetime                    # tz-aware: when the session ended
    scores: dict[str, int | None]     # DIMENSIONS -> 0-100 or None
    duration_seconds: float
    turns: int
    words: int
    praise: int


def local_day(when: datetime, tz_offset_minutes: int) -> date:
    return (when.astimezone(timezone.utc) + timedelta(minutes=tz_offset_minutes)).date()


def week_start(day: date) -> date:
    """The Monday of `day`'s week."""
    return day - timedelta(days=day.weekday())


def _mean(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


# ── Weekly trend ──────────────────────────────────────────────────────────────

def weekly(points: list[Point], weeks: int, today: date, tz_offset_minutes: int) -> list[dict]:
    """
    One entry per week for the last `weeks` weeks (oldest first, empty weeks included
    so the chart has honest gaps): the week's session count, practice time and the
    average of each score.
    """
    this_monday = week_start(today)
    starts = [this_monday - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
    buckets: dict[date, list[Point]] = {s: [] for s in starts}
    for p in points:
        monday = week_start(local_day(p.when, tz_offset_minutes))
        if monday in buckets:
            buckets[monday].append(p)

    out = []
    for monday in starts:
        group = buckets[monday]
        entry = {
            "week_start": monday.isoformat(),
            "sessions": len(group),
            "practice_seconds": round(sum(p.duration_seconds for p in group)),
        }
        for dim in DIMENSIONS:
            entry[dim] = _mean([p.scores[dim] for p in group if p.scores.get(dim) is not None])
        out.append(entry)
    return out


# ── Streak ────────────────────────────────────────────────────────────────────

def streaks(points: list[Point], today: date, tz_offset_minutes: int) -> dict:
    """
    Consecutive days with at least one session. The current streak stays alive
    through today even if you haven't practised yet (it only breaks once a whole
    day is missed), so opening the page in the morning doesn't show a zero.
    """
    days = {local_day(p.when, tz_offset_minutes) for p in points}

    longest = run = 0
    previous = None
    for day in sorted(days):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day

    current = 0
    cursor = today if today in days else today - timedelta(days=1)
    while cursor in days:
        current += 1
        cursor -= timedelta(days=1)

    return {
        "current": current,
        "longest": longest,
        "practiced_today": today in days,
        "last_7_days": [(today - timedelta(days=i)) in days for i in range(6, -1, -1)],  # oldest first
    }


# ── Milestones ────────────────────────────────────────────────────────────────

def _trend_milestones(points: list[Point]) -> list[dict]:
    if len(points) < MIN_SESSIONS_FOR_TREND:
        return []
    ordered = sorted(points, key=lambda p: p.when)
    early, late = ordered[:TREND_GROUP], ordered[-TREND_GROUP:]
    span_days = (sum(p.when.timestamp() for p in late) / len(late) - sum(p.when.timestamp() for p in early) / len(early)) / 86400
    weeks_span = max(1, round(span_days / 7))

    gains = []
    for dim in DIMENSIONS[1:]:   # the five specific dimensions; "overall" is told separately
        before = _mean([p.scores[dim] for p in early if p.scores.get(dim) is not None])
        after = _mean([p.scores[dim] for p in late if p.scores.get(dim) is not None])
        if before is not None and after is not None and after - before >= MIN_GAIN_TO_CELEBRATE:
            gains.append((after - before, dim))
    gains.sort(reverse=True)
    return [
        {
            "kind": "improvement", "dimension": dim, "delta": delta, "weeks": weeks_span,
            "text": f"Your {dim} improved by {delta} points over {weeks_span} {'week' if weeks_span == 1 else 'weeks'}",
        }
        for delta, dim in gains[:2]
    ]


def milestones(points: list[Point], streak: dict, totals: dict) -> list[dict]:
    """The most celebration-worthy things, most notable first (at most MAX_MILESTONES)."""
    found: list[dict] = []

    found += _trend_milestones(points)

    reached = [n for n in STREAK_MILESTONES if streak["current"] >= n]
    if reached:
        found.append({"kind": "streak", "value": reached[-1], "text": f"{reached[-1]}-day practice streak"})

    scored = sorted((p for p in points if p.scores.get("overall") is not None), key=lambda p: p.when)
    if len(scored) >= 3:
        latest, previous_best = scored[-1], max(p.scores["overall"] for p in scored[:-1])
        if latest.scores["overall"] > previous_best:
            found.append({"kind": "personal_best", "value": latest.scores["overall"], "text": f"New personal best: {latest.scores['overall']} overall"})

    hours = totals["practice_seconds"] / 3600
    reached_hours = [h for h in PRACTICE_HOUR_MILESTONES if hours >= h]
    if reached_hours:
        h = reached_hours[-1]
        found.append({"kind": "practice_time", "value": h, "text": f"{h} {'hour' if h == 1 else 'hours'} of speaking practice"})

    reached_sessions = [n for n in SESSION_MILESTONES if totals["sessions"] >= n]
    if reached_sessions:
        n = reached_sessions[-1]
        found.append({"kind": "sessions", "value": n, "text": "First session complete" if n == 1 else f"{n} sessions completed"})

    return found[:MAX_MILESTONES]


# ── Everything the page needs ─────────────────────────────────────────────────

def summarize(points: list[Point], now: datetime, tz_offset_minutes: int = 0, weeks: int = 12) -> dict:
    today = local_day(now, tz_offset_minutes)
    ordered = sorted(points, key=lambda p: p.when)

    totals = {
        "sessions": len(ordered),
        "practice_seconds": round(sum(p.duration_seconds for p in ordered)),
        "turns": sum(p.turns for p in ordered),
        "words": sum(p.words for p in ordered),
        "praise": sum(p.praise for p in ordered),
    }
    streak = streaks(ordered, today, tz_offset_minutes)

    scored = [p for p in ordered if p.scores.get("overall") is not None]
    best = max(scored, key=lambda p: p.scores["overall"]) if scored else None

    return {
        "has_data": bool(ordered),
        "totals": totals,
        "streak": streak,
        "weekly": weekly(ordered, weeks, today, tz_offset_minutes),
        "milestones": milestones(ordered, streak, totals),
        "best_session": {"conversation_id": best.conversation_id, "overall": best.scores["overall"], "when": best.when.isoformat()} if best else None,
        "recent": [
            {"conversation_id": p.conversation_id, "when": p.when.isoformat(), "overall": p.scores.get("overall"),
             "turns": p.turns, "duration_seconds": round(p.duration_seconds)}
            for p in reversed(ordered[-8:])
        ],
    }
