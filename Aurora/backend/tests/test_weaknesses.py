"""Weakness profiling, today's exercise, and steering a session toward a focus."""
from datetime import datetime, timedelta, timezone

import pytest

from backend import taxonomy
from backend.database import SessionLocal
from backend.models.reports import UserWeakness
from backend.personalities import STYLE_GUARDRAILS, build_system_prompt
from backend.services import reports, weaknesses
from backend.services.weaknesses import Mistake
from backend.tests.test_reports import finished_session

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def m(subtype="past_tense", days_ago=1, category="grammar", conversation="c1"):
    return Mistake(category=category, subtype=subtype, when=NOW - timedelta(days=days_ago), conversation_id=conversation)


def sessions(*days_ago):
    return [NOW - timedelta(days=d) for d in days_ago]


# ── The maths ─────────────────────────────────────────────────────────────────

def test_mistakes_are_grouped_and_counted_with_their_windows():
    ws = weaknesses.compute([m(days_ago=1), m(days_ago=5), m(days_ago=40), m(days_ago=70), m("articles", days_ago=2)], sessions(1, 5), NOW)
    past = next(w for w in ws if w.subtype == "past_tense")
    assert (past.occurrence_count, past.recent_count, past.previous_count) == (4, 2, 1)       # the 70-day-old one is in neither window
    assert past.first_seen_at == NOW - timedelta(days=70) and past.last_seen_at == NOW - timedelta(days=1)


def test_the_window_boundary_is_exactly_30_days():
    ws = weaknesses.compute([m(days_ago=29.9), m(days_ago=30.1)], sessions(1), NOW)
    assert (ws[0].recent_count, ws[0].previous_count) == (1, 1)


def test_sessions_seen_counts_distinct_sessions():
    ws = weaknesses.compute([m(conversation="a"), m(conversation="a"), m(conversation="b")], sessions(1, 2), NOW)
    assert ws[0].sessions_seen == 2


def test_ranking_weights_recent_mistakes_more_than_old_ones_and_breaks_ties_by_recency():
    old_habit = [m("tense", days_ago=d) for d in (40, 45, 50, 55, 60, 65)]                  # 6 old mistakes -> priority 6
    new_habit = [m("articles", days_ago=d) for d in (1, 2, 3)]                              # 3 recent -> priority 9
    ws = weaknesses.compute(old_habit + new_habit, sessions(1, 2, 3, 45), NOW)
    assert [w.subtype for w in ws] == ["articles", "tense"] and ws[0].priority == 9.0
    tie = weaknesses.compute([m("plurals", days_ago=3), m("pronouns", days_ago=1)], sessions(1), NOW)
    assert [w.subtype for w in tie] == ["pronouns", "plurals"]


# ── The trend ─────────────────────────────────────────────────────────────────

def trend_of(mistakes, session_days):
    return weaknesses.compute(mistakes, sessions(*session_days), NOW)[0].trend


def test_a_brand_new_weakness_is_new():
    assert trend_of([m(days_ago=3), m(days_ago=4)], (3, 4)) == "new"


def test_a_weakness_that_stopped_is_improving():
    earlier = [m(days_ago=d) for d in (35, 38, 42, 50)]
    assert trend_of(earlier, (3, 5, 36, 40, 45)) == "improving"        # four mistakes a month ago, none lately


def test_a_weakness_that_got_more_frequent_per_session_is_worsening():
    mistakes = [m(days_ago=40)] * 2 + [m(days_ago=d) for d in (1, 2, 3, 4, 5, 6)]
    assert trend_of(mistakes, (1, 3, 5, 38, 42, 44)) == "worsening"    # 2 per 3 sessions -> 6 per 3 sessions


def test_practising_more_is_not_getting_worse():
    """Double the mistakes in a month with FIVE times the sessions is a lower rate, not a decline."""
    mistakes = [m(days_ago=d) for d in (35, 36, 37, 38)] + [m(days_ago=d) for d in range(1, 9)]
    sess = (35, 40) + tuple(range(1, 11))
    assert trend_of(mistakes, sess) != "worsening"
    assert trend_of(mistakes, sess) == "improving"                     # 4 per 2 sessions (2.0) -> 8 per 10 sessions (0.8)


def test_without_recent_practice_nothing_is_called_improving():
    assert trend_of([m(days_ago=d) for d in (40, 45, 50)], (40, 45, 50)) == "stable"


def test_a_couple_of_mistakes_is_too_little_to_call_a_trend():
    assert trend_of([m(days_ago=40), m(days_ago=2)], (2, 40)) == "stable"


def test_an_unchanged_rate_is_stable():
    mistakes = [m(days_ago=d) for d in (35, 40, 2, 5)]
    assert trend_of(mistakes, (35, 40, 2, 5)) == "stable"


# ── Database ──────────────────────────────────────────────────────────────────

def old(days):
    return datetime.now(timezone.utc) - timedelta(days=days)


def test_only_mistakes_count_not_suggestions_or_praise(db, user):
    uid = user["user"]["id"]
    finished_session(uid, corrections=[
        dict(),                                                                                                  # a mistake
        dict(subtype="weak_vocabulary", category="naturalness", is_error=False),                                 # a suggestion
        dict(subtype="idiom_used", category="naturalness", is_error=False, is_positive=True),                    # praise
    ])
    rows = weaknesses.recompute(db, uid)
    assert [(r.category, r.subtype) for r in rows] == [("grammar", "past_tense")]


def test_recompute_is_idempotent_and_replaces_stale_rows(db, user):
    uid = user["user"]["id"]
    finished_session(uid, corrections=[dict(), dict(subtype="articles")])
    first = weaknesses.recompute(db, uid)
    second = weaknesses.recompute(db, uid)
    assert len(first) == len(second) == 2 and db.query(UserWeakness).filter_by(user_id=uid).count() == 2


def test_profiles_are_per_user(db, user, make_user):
    other = make_user("other@example.com")
    finished_session(user["user"]["id"], corrections=[dict()])
    weaknesses.recompute(db, user["user"]["id"])
    assert weaknesses.get_profile(db, other["user"]["id"]) == []


def test_the_profile_is_built_on_first_use_then_served_from_the_cache(db, user, monkeypatch):
    uid = user["user"]["id"]
    finished_session(uid, corrections=[dict()])
    assert db.query(UserWeakness).count() == 0
    assert len(weaknesses.get_profile(db, uid)) == 1 and db.query(UserWeakness).count() == 1       # built lazily

    monkeypatch.setattr(weaknesses, "recompute", lambda *a, **k: pytest.fail("a fresh cache must not be rebuilt"))
    assert len(weaknesses.get_profile(db, uid)) == 1


def test_a_stale_cache_is_rebuilt_because_the_windows_move(db, user):
    uid = user["user"]["id"]
    finished_session(uid, corrections=[dict(created_at=old(29))])                       # recent today...
    assert weaknesses.get_profile(db, uid)[0].recent_count == 1
    db.query(UserWeakness).update({"updated_at": datetime.now(timezone.utc) - timedelta(hours=2)})
    db.commit()
    later = datetime.now(timezone.utc) + timedelta(days=3)                              # ...but not three days on
    assert weaknesses.get_profile(db, uid, now=later)[0].recent_count == 0


def test_generating_a_report_refreshes_the_profile(db, user, ai):
    uid = user["user"]["id"]
    cid = finished_session(uid, corrections=[dict(), dict(subtype="articles")])
    assert db.query(UserWeakness).count() == 0
    reports.generate_report(cid)
    assert db.query(UserWeakness).filter_by(user_id=uid).count() == 2


def test_backfilling_old_sessions_rebuilds_the_profile_once(db, user, ai, monkeypatch):
    uid = user["user"]["id"]
    for d in (1, 2, 3):
        finished_session(uid, ended_seconds_ago=d * 86400, corrections=[dict()])
    calls = []
    real = weaknesses.recompute
    monkeypatch.setattr(weaknesses, "recompute", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    assert reports.backfill_missing(uid) == 3
    assert len(calls) == 1 and db.query(UserWeakness).filter_by(user_id=uid).one().occurrence_count == 3


def test_a_profiling_failure_never_breaks_a_report(db, user, ai, monkeypatch):
    cid = finished_session(user["user"]["id"], corrections=[dict()])
    monkeypatch.setattr(weaknesses, "recompute", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert reports.generate_report(cid)["scores"]["overall"] is not None


# ── Today's exercise ──────────────────────────────────────────────────────────

def w(subtype, recent, occurrences=None, trend="stable", category="grammar"):
    now = datetime.now(timezone.utc)
    return UserWeakness(user_id="u", category=category, subtype=subtype, occurrence_count=occurrences or recent, recent_count=recent,
                        previous_count=0, sessions_seen=1, priority=float(recent * 3), trend=trend, first_seen_at=now, last_seen_at=now, updated_at=now)


def test_the_top_live_weakness_is_chosen_and_explained():
    ex = weaknesses.today_exercise([w("past_tense", 6), w("articles", 2)])
    assert ex["focus"] == "grammar:past_tense" and ex["label"] == "Past tense" and ex["suggested_scenario"] == "casual"
    assert ex["why"] == "6 past tense mistakes in the last 30 days"


def test_wording_adapts_to_count_and_trend():
    assert weaknesses.today_exercise([w("articles", 1)])["why"] == "1 articles (a, an, the) mistake in the last 30 days"
    assert weaknesses.today_exercise([w("articles", 3, trend="improving")])["why"].endswith("— and improving. Keep it up.")
    assert weaknesses.today_exercise([w("articles", 3, trend="worsening")])["why"].endswith("it's been slipping lately.")


def test_the_catch_all_bucket_is_never_the_exercise():
    ex = weaknesses.today_exercise([w("other", 9), w("articles", 1)])
    assert ex["subtype"] == "articles"
    assert weaknesses.today_exercise([w("other", 9)]) is None


def test_an_old_weakness_with_nothing_recent_is_only_a_fallback():
    stale_big, recent_small = w("tense", 0, occurrences=20), w("pronouns", 1)
    assert weaknesses.today_exercise([stale_big, recent_small])["subtype"] == "pronouns"          # still live beats historically bigger
    fallback = weaknesses.today_exercise([stale_big])
    assert fallback["subtype"] == "tense" and "refresher" in fallback["why"]


def test_no_history_means_no_exercise():
    assert weaknesses.today_exercise([]) is None


# ── The endpoints ─────────────────────────────────────────────────────────────

def test_practice_endpoints_require_auth(client):
    assert client.get("/api/practice/today").status_code == 401
    assert client.get("/api/practice/weaknesses").status_code == 401


def test_a_new_learner_gets_a_starter(client, user):
    body = client.get("/api/practice/today", headers=user["headers"]).json()
    assert body["has_focus"] is False and body["exercise"]["focus"] is None and body["exercise"]["suggested_scenario"] == "casual"
    assert client.get("/api/practice/weaknesses", headers=user["headers"]).json() == {"weaknesses": []}


def test_today_and_weaknesses_reflect_the_mistake_history(client, user):
    finished_session(user["user"]["id"], corrections=[dict(), dict(), dict(subtype="articles")])
    today = client.get("/api/practice/today", headers=user["headers"]).json()
    assert today["has_focus"] and today["exercise"]["focus"] == "grammar:past_tense"
    listed = client.get("/api/practice/weaknesses", headers=user["headers"]).json()["weaknesses"]
    assert [x["subtype"] for x in listed] == ["past_tense", "articles"]
    assert listed[0]["label"] == "Past tense" and listed[0]["occurrences"] == 2 and listed[0]["focus"] == "grammar:past_tense"


# ── Steering a session ────────────────────────────────────────────────────────

def test_a_session_can_start_with_a_focus(client, user, start_session, db):
    from backend.models.core import Conversation

    cid = start_session(user["headers"], focus="grammar:past_tense")
    assert db.get(Conversation, cid).focus == "grammar:past_tense"


@pytest.mark.parametrize("bad", ["grammar:nonsense", "nonsense:past_tense", "past_tense", ":", "grammar:"])
def test_a_made_up_focus_is_refused(client, user, bad):
    assert client.post("/api/conversation/start", headers=user["headers"], data={"focus": bad}).status_code == 400


def test_the_focus_steers_the_coach_silently(user, start_session, ai, post_turn):
    post_turn(user["headers"], start_session(user["headers"], focus="grammar:past_tense"))
    system = ai.llm_calls[0][0]["content"]
    assert "already happened" in system                                  # the taxonomy's steering text for past tense
    assert "NEVER mention this focus" in system


def test_no_focus_means_no_steering(user, start_session, ai, post_turn):
    post_turn(user["headers"], start_session(user["headers"]))
    assert "PRACTICE FOCUS" not in ai.llm_calls[0][0]["content"]


def test_parse_focus():
    assert taxonomy.parse_focus("grammar:past_tense") == ("grammar", "past_tense")
    assert taxonomy.parse_focus("naturalness:idiom_used") == ("naturalness", "idiom_used")
    assert taxonomy.parse_focus(None) is None and taxonomy.parse_focus("") is None
    assert taxonomy.focus_id("grammar", "articles") == "grammar:articles"


def test_every_weakness_has_a_scenario_that_exists():
    from backend.personalities import SCENARIOS

    assert set(taxonomy.PRACTICE_SCENARIO.values()) <= set(SCENARIOS)
    assert taxonomy.scenario_for("something_unknown") == "casual"


# ── The prompt builder ────────────────────────────────────────────────────────

def test_regional_styles_carry_the_guardrails_but_standard_english_does_not():
    """Regression: STYLE_GUARDRAILS was defined and documented as 'appended to every non-standard style' but never was."""
    assert STYLE_GUARDRAILS in build_system_prompt(style="irish")
    assert "never exaggerate" in build_system_prompt(style="british").lower()
    assert STYLE_GUARDRAILS not in build_system_prompt(style="standard")
    assert STYLE_GUARDRAILS not in build_system_prompt(style="not-a-style")


def test_the_prompt_builder_keeps_its_old_behaviour_by_default():
    prompt = build_system_prompt(scenario="interview", style="standard")
    assert "interviewer" in prompt.lower() and "DIFFICULTY" not in prompt and "FOCUS" not in prompt


def test_difficulty_and_focus_clauses():
    prompt = build_system_prompt(difficulty=4, focus="things that already happened")
    assert "DIFFICULTY (Upper-Intermediate)" in prompt and "things that already happened" in prompt
    assert "DIFFICULTY" not in build_system_prompt(difficulty=99)             # unknown levels are ignored
