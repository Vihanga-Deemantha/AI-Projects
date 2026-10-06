"""Progress: weekly trends, streaks, milestones (pure maths) and the endpoint."""
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.services import progress
from backend.services.progress import Point
from backend.tests.test_reports import finished_session, mistake

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)      # a Wednesday
TODAY = NOW.date()


def pt(days_ago=0, hours=0, overall=80, minutes=10, **dims):
    when = NOW - timedelta(days=days_ago, hours=hours)
    scores = {d: dims.get(d, overall) for d in progress.DIMENSIONS}
    scores["overall"] = overall
    return Point(conversation_id=f"c-{days_ago}-{hours}-{overall}", when=when, scores=scores,
                 duration_seconds=minutes * 60, turns=5, words=100, praise=1)


# ── Days and weeks belong to the learner ──────────────────────────────────────

def test_a_late_night_session_is_still_today_in_the_learners_timezone():
    late = datetime(2026, 10, 7, 20, 0, tzinfo=timezone.utc)          # 20:00 UTC...
    assert progress.local_day(late, 0) == date(2026, 10, 7)
    assert progress.local_day(late, 330) == date(2026, 10, 8)          # ...is 01:30 tomorrow in India (UTC+5:30)
    assert progress.local_day(late, -300) == date(2026, 10, 7)         # ...and 15:00 today in New York (UTC-5)


def test_weeks_start_on_monday():
    assert progress.week_start(date(2026, 10, 7)) == date(2026, 10, 5)  # Wednesday -> Monday
    assert progress.week_start(date(2026, 10, 5)) == date(2026, 10, 5)
    assert progress.week_start(date(2026, 10, 11)) == date(2026, 10, 5)  # Sunday belongs to the week before


# ── Weekly trend ──────────────────────────────────────────────────────────────

def test_weekly_returns_every_week_oldest_first_with_honest_gaps():
    points = [pt(days_ago=1, overall=70), pt(days_ago=2, overall=90), pt(days_ago=22, overall=60)]
    weeks = progress.weekly(points, 4, TODAY, 0)
    assert [w["week_start"] for w in weeks] == ["2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05"]
    assert [w["sessions"] for w in weeks] == [1, 0, 0, 2]
    assert weeks[0]["overall"] == 60 and weeks[1]["overall"] is None and weeks[2]["overall"] is None   # an empty week is None, not 0
    assert weeks[3]["overall"] == 80                                                                   # mean of 70 and 90


def test_weekly_averages_ignore_missing_dimensions():
    a, b = pt(days_ago=1, fluency=None), pt(days_ago=2, fluency=60)
    a.scores["fluency"] = None
    assert progress.weekly([a, b], 4, TODAY, 0)[-1]["fluency"] == 60


def test_weekly_adds_up_practice_time_and_drops_sessions_outside_the_window():
    weeks = progress.weekly([pt(days_ago=1, minutes=10), pt(days_ago=2, minutes=5), pt(days_ago=200)], 4, TODAY, 0)
    assert weeks[-1]["practice_seconds"] == 15 * 60 and sum(w["sessions"] for w in weeks) == 2


# ── Streaks ───────────────────────────────────────────────────────────────────

def test_streak_counts_consecutive_days_up_to_today():
    s = progress.streaks([pt(0), pt(1), pt(2)], TODAY, 0)
    assert (s["current"], s["longest"], s["practiced_today"]) == (3, 3, True)


def test_the_streak_is_still_alive_if_you_have_not_practised_yet_today():
    s = progress.streaks([pt(1), pt(2)], TODAY, 0)
    assert (s["current"], s["practiced_today"]) == (2, False)


def test_a_missed_day_breaks_the_streak_but_not_the_record():
    s = progress.streaks([pt(2), pt(3), pt(4), pt(5)], TODAY, 0)       # nothing yesterday or today
    assert (s["current"], s["longest"]) == (0, 4)


def test_longest_streak_spans_gaps():
    s = progress.streaks([pt(0), pt(1), pt(5), pt(6), pt(7), pt(8)], TODAY, 0)
    assert (s["current"], s["longest"]) == (2, 4)


def test_several_sessions_in_a_day_count_once():
    assert progress.streaks([pt(0, hours=1), pt(0, hours=2), pt(1)], TODAY, 0)["current"] == 2


def test_the_week_strip_is_oldest_first():
    s = progress.streaks([pt(0), pt(2), pt(6)], TODAY, 0)
    assert s["last_7_days"] == [True, False, False, False, True, False, True]   # 6 days ago ... today


def test_the_timezone_decides_which_day_a_session_belongs_to():
    late = Point("c", datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc), {d: 80 for d in progress.DIMENSIONS}, 60, 1, 10, 0)
    # In UTC this is Oct 6; in India (UTC+5:30) it is already Oct 7 — "today" for a learner whose today is Oct 7.
    assert progress.streaks([late], date(2026, 10, 7), 0)["practiced_today"] is False
    assert progress.streaks([late], date(2026, 10, 7), 330)["practiced_today"] is True


# ── Milestones ────────────────────────────────────────────────────────────────

def improving(gain=15, n=6):
    """n sessions over ~5 weeks, rising by `gain` fluency points from the first to the last."""
    return [pt(days_ago=(n - 1 - i) * 7, overall=70, fluency=60 + round(gain * i / (n - 1))) for i in range(n)]


def totals_of(points):
    return {"sessions": len(points), "practice_seconds": sum(p.duration_seconds for p in points)}


def test_a_real_improvement_is_celebrated_with_the_points_and_the_span():
    # Fluency rises 60 -> 90 over six weekly sessions: 60,66,72 | 78,84,90. The earliest three average 66,
    # the latest three 84, so the gain is 18 points, measured over the 3 weeks between those groups' centres.
    pts = improving(gain=30)
    found = progress.milestones(pts, progress.streaks(pts, TODAY, 0), totals_of(pts))
    top = found[0]
    assert (top["kind"], top["dimension"], top["delta"], top["weeks"]) == ("improvement", "fluency", 18, 3)
    assert top["text"] == "Your fluency improved by 18 points over 3 weeks"


def test_small_changes_and_too_little_data_are_not_celebrated():
    flat = improving(gain=3)
    assert not [m for m in progress.milestones(flat, progress.streaks(flat, TODAY, 0), totals_of(flat)) if m["kind"] == "improvement"]
    few = improving(gain=30, n=3)
    assert not [m for m in progress.milestones(few, progress.streaks(few, TODAY, 0), totals_of(few)) if m["kind"] == "improvement"]


def test_a_decline_is_never_presented_as_a_milestone():
    falling = improving(gain=-20)
    assert not [m for m in progress.milestones(falling, progress.streaks(falling, TODAY, 0), totals_of(falling)) if m["kind"] == "improvement"]


def test_streak_milestones_name_the_highest_threshold_reached():
    pts = [pt(i) for i in range(8)]
    found = progress.milestones(pts, progress.streaks(pts, TODAY, 0), totals_of(pts))
    assert {"kind": "streak", "value": 7, "text": "7-day practice streak"} in found


def test_a_personal_best_needs_a_history_and_must_beat_it():
    best = [pt(10, overall=70), pt(5, overall=75), pt(0, overall=90)]
    assert any(m["kind"] == "personal_best" and m["value"] == 90 for m in progress.milestones(best, progress.streaks(best, TODAY, 0), totals_of(best)))
    not_best = [pt(10, overall=90), pt(5, overall=75), pt(0, overall=80)]
    assert not any(m["kind"] == "personal_best" for m in progress.milestones(not_best, progress.streaks(not_best, TODAY, 0), totals_of(not_best)))
    assert not any(m["kind"] == "personal_best" for m in progress.milestones(best[1:], progress.streaks(best[1:], TODAY, 0), totals_of(best[1:])))


def test_practice_time_and_session_count_milestones():
    pts = [pt(i * 3, minutes=40) for i in range(3)]                    # 2 hours in 3 sessions
    texts = [m["text"] for m in progress.milestones(pts, progress.streaks(pts, TODAY, 0), totals_of(pts))]
    assert "1 hour of speaking practice" in texts
    first = [pt(0)]
    assert "First session complete" in [m["text"] for m in progress.milestones(first, progress.streaks(first, TODAY, 0), totals_of(first))]


def test_at_most_four_milestones_with_improvements_first():
    pts = [pt(days_ago=i, overall=60 + i, fluency=95 - i * 4, grammar=95 - i * 4) for i in range(30)]
    found = progress.milestones(pts, progress.streaks(pts, TODAY, 0), totals_of(pts))
    assert len(found) <= progress.MAX_MILESTONES
    assert found[0]["kind"] == "improvement"


# ── Summary ───────────────────────────────────────────────────────────────────

def test_an_empty_history_is_not_an_error():
    s = progress.summarize([], NOW, 0, weeks=8)
    assert s["has_data"] is False and s["totals"]["sessions"] == 0 and len(s["weekly"]) == 8
    assert s["best_session"] is None and s["recent"] == [] and s["milestones"] == [] and s["streak"]["current"] == 0


def test_the_summary_totals_best_session_and_recent_list():
    pts = [pt(days_ago=d, overall=o) for d, o in ((9, 60), (6, 95), (3, 70), (0, 80))]
    s = progress.summarize(pts, NOW, 0)
    assert s["totals"] == {"sessions": 4, "practice_seconds": 2400, "turns": 20, "words": 400, "praise": 4}
    assert s["best_session"]["overall"] == 95
    assert [r["overall"] for r in s["recent"]] == [80, 70, 95, 60]       # newest first


def test_the_recent_list_is_capped():
    assert len(progress.summarize([pt(i) for i in range(20)], NOW)["recent"]) == 8


# ── The endpoint ──────────────────────────────────────────────────────────────

def test_progress_requires_auth(client):
    assert client.get("/api/progress/summary").status_code == 401


def test_a_new_learner_has_an_empty_but_valid_summary(client, user):
    r = client.get("/api/progress/summary", headers=user["headers"])
    assert r.status_code == 200 and r.json()["has_data"] is False and len(r.json()["weekly"]) == 12


@pytest.mark.parametrize("query", ["weeks=3", "weeks=53", "tz_offset=900", "tz_offset=-900"])
def test_progress_validates_its_parameters(client, user, query):
    assert client.get(f"/api/progress/summary?{query}", headers=user["headers"]).status_code == 422


def test_progress_reflects_finished_sessions(client, user, ai):
    finished_session(user["user"]["id"], ended_seconds_ago=3600, corrections=[mistake()])
    finished_session(user["user"]["id"], ended_seconds_ago=86400 + 3600, corrections=[mistake(), mistake(subtype="articles")])
    s = client.get("/api/progress/summary?weeks=4", headers=user["headers"]).json()
    assert s["has_data"] and s["totals"]["sessions"] == 2 and s["totals"]["turns"] == 4
    assert s["streak"]["longest"] >= 2
    assert sum(w["sessions"] for w in s["weekly"]) == 2
    assert s["best_session"]["overall"] is not None


def test_old_sessions_get_reports_backfilled_without_spending_llm_calls(client, user, ai, db):
    from backend.models.reports import SessionReport

    for days in (1, 2, 3):
        finished_session(user["user"]["id"], ended_seconds_ago=days * 86400, corrections=[mistake()])
    assert db.query(SessionReport).count() == 0
    s = client.get("/api/progress/summary", headers=user["headers"]).json()
    assert db.query(SessionReport).count() == 3 and s["totals"]["sessions"] == 3
    assert ai.summary_calls == []                       # back-filling must not fire a burst of LLM calls


def test_sessions_that_were_never_analysed_count_as_practice_but_not_as_scores(client, user, ai):
    """A pre-analysis session has no corrections and no metrics: that is 'unknown', not 'perfect'."""
    finished_session(user["user"]["id"], ended_seconds_ago=3600)                       # nothing recorded
    finished_session(user["user"]["id"], ended_seconds_ago=7200, corrections=[mistake()])
    s = client.get("/api/progress/summary", headers=user["headers"]).json()
    assert s["totals"]["sessions"] == 2                                                 # both were practice
    scored = [w["overall"] for w in s["weekly"] if w["overall"] is not None]
    assert len(scored) == 1 and scored[0] < 100                                         # only the analysed one has a score


def _offsets_for_midnight_test(now: datetime) -> tuple[int, int]:
    """
    Two UTC offsets (minutes, within the API's ±840) chosen from the clock so the test means the same at any hour:
    one whose local clock has just passed midnight (reads 00:05), and one half a day away (reads 12:05).
    """
    minutes_into_utc_day = now.hour * 60 + now.minute
    just_after_midnight = (5 - minutes_into_utc_day) % 1440
    if just_after_midnight > 840:
        just_after_midnight -= 1440
    midday = just_after_midnight + 720 if just_after_midnight <= 120 else just_after_midnight - 720
    return just_after_midnight, midday


def test_the_clock_the_offsets_are_chosen_from_stays_within_the_api_range_at_every_minute_of_the_day():
    for minute in range(1440):
        now = datetime(2026, 10, 7, minute // 60, minute % 60, tzinfo=timezone.utc)
        after_midnight, midday = _offsets_for_midnight_test(now)
        assert -840 <= after_midnight <= 840 and -840 <= midday <= 840
        for offset, expected_clock in ((after_midnight, 5), (midday, 12 * 60 + 5)):
            assert (minute + offset) % 1440 == expected_clock


def test_the_timezone_parameter_moves_the_day_boundary(client, user, ai):
    """
    The same session is "today" in one time zone and "yesterday" in another. It ended 15 minutes ago: where the clock
    has just passed midnight (00:05) that was before midnight, so a different day; where it reads 12:05 it was the same
    day. The offsets are worked out from the current time, so the test holds at any hour of the day (an earlier version
    assumed UTC+5:30 was still on the same date as UTC, which is only so before 18:30 UTC).
    """
    after_midnight, midday = _offsets_for_midnight_test(datetime.now(timezone.utc))
    finished_session(user["user"]["id"], ended_seconds_ago=15 * 60, corrections=[mistake()])
    across_midnight = client.get(f"/api/progress/summary?tz_offset={after_midnight}", headers=user["headers"]).json()["streak"]
    same_day = client.get(f"/api/progress/summary?tz_offset={midday}", headers=user["headers"]).json()["streak"]
    assert across_midnight["practiced_today"] is False and same_day["practiced_today"] is True


def test_progress_is_private_to_the_learner(client, user, make_user, ai):
    finished_session(user["user"]["id"], corrections=[mistake()])
    other = make_user("other@example.com")
    assert client.get("/api/progress/summary", headers=other["headers"]).json()["has_data"] is False
