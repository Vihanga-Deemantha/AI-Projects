"""Adaptive difficulty: choosing the tier, pinning one, and the coach actually using it."""
import random
from datetime import datetime, timedelta, timezone

import pytest

from backend.database import SessionLocal
from backend.models.core import Conversation, User
from backend.models.reports import SessionReport
from backend.personalities import DEFAULT_DIFFICULTY, DIFFICULTY_LEVELS, build_system_prompt
from backend.services import difficulty, scoring


def scored_session(user_id: str, overall: int | None, ended_seconds_ago: int = 3600) -> str:
    """A finished session with a report, built straight in the database (its content isn't the point here)."""
    ended = datetime.now(timezone.utc) - timedelta(seconds=ended_seconds_ago)
    with SessionLocal() as s:
        c = Conversation(user_id=user_id, started_at=ended - timedelta(seconds=90), ended_at=ended, is_complete=True)
        s.add(c)
        s.flush()
        s.add(SessionReport(conversation_id=c.id, user_id=user_id, scoring_version=scoring.SCORING_VERSION,
                            overall_score=overall, total_turns=2, total_words=24))
        s.commit()
        return c.id


def history(user_id: str, *scores: int | None) -> None:
    """Gives the learner sessions with these scores, OLDEST first (a day apart, the last one ended yesterday)."""
    for i, score in enumerate(scores):
        scored_session(user_id, score, ended_seconds_ago=86400 * (len(scores) - i))


def level(client, headers) -> dict:
    r = client.get("/api/practice/difficulty", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ── Choosing a tier (the maths) ───────────────────────────────────────────────

@pytest.mark.parametrize("average, tier", [(100, 5), (90, 5), (89, 4), (78, 4), (77, 3), (65, 3), (64, 2), (50, 2), (49, 1), (0, 1)])
def test_the_thresholds(average, tier):
    assert difficulty.tier_for_scores([average]) == tier


def test_the_average_decides_not_the_latest_score():
    assert difficulty.tier_for_scores([95, 60, 70]) == 3                  # 75
    assert difficulty.tier_for_scores([89, 90]) == 4                      # 89.5 is under 90
    assert difficulty.tier_for_scores([100, 80]) == 5                     # 90 exactly


def test_with_no_scores_the_default_tier_is_used():
    assert difficulty.tier_for_scores([]) == DEFAULT_DIFFICULTY


def test_the_thresholds_only_name_real_tiers_and_descend():
    minimums = [m for m, _ in difficulty.THRESHOLDS]
    assert minimums == sorted(minimums, reverse=True) and len(set(minimums)) == len(minimums)
    assert all(t in DIFFICULTY_LEVELS for _, t in difficulty.THRESHOLDS)
    assert (difficulty.MIN_TIER, difficulty.MAX_TIER) == (1, 5) and DEFAULT_DIFFICULTY in DIFFICULTY_LEVELS
    assert [t for _, t in difficulty.THRESHOLDS] == sorted(DIFFICULTY_LEVELS, reverse=True)[:-1]   # every tier above the lowest is reachable


def test_a_step_is_one_tier_toward_the_target_and_no_more():
    assert difficulty.step_toward(2, 5) == 3 and difficulty.step_toward(4, 1) == 3
    assert difficulty.step_toward(3, 3) == 3
    assert difficulty.step_toward(5, 9) == 5 and difficulty.step_toward(1, 0) == 1     # clamped to the real range


def test_a_strong_learner_climbs_one_tier_per_session_until_the_top():
    assert difficulty.tier_history([95] * 5) == [3, 4, 5, 5, 5]


def test_a_struggling_learner_sinks_to_the_bottom_and_stays():
    assert difficulty.tier_history([30] * 4) == [1, 1, 1, 1]


def test_a_steady_learner_settles_where_their_scores_put_them():
    assert difficulty.tier_history([70] * 4) == [3, 3, 3, 3]


def test_one_great_session_does_not_leap_the_level():
    assert difficulty.tier_history([40, 40, 40, 100]) == [1, 1, 1, 2]       # the average is 60: tier 2, one step up


def test_one_bad_session_does_not_crash_the_level():
    assert difficulty.tier_history([95, 95, 95, 0]) == [3, 4, 5, 4]         # the average is 63: tier 2, but only one step down


def test_no_sessions_means_no_history():
    assert difficulty.tier_history([]) == []


def test_the_history_is_a_replay_so_new_sessions_never_rewrite_the_past():
    rng = random.Random(1234)
    for _ in range(200):
        scores = [rng.randint(0, 100) for _ in range(rng.randint(0, 15))]
        tiers = difficulty.tier_history(scores)
        assert len(tiers) == len(scores)
        previous = DEFAULT_DIFFICULTY
        for i, tier in enumerate(tiers):
            assert difficulty.MIN_TIER <= tier <= difficulty.MAX_TIER
            assert abs(tier - previous) <= 1                                     # at most one step per session
            target = difficulty.tier_for_scores(scores[max(0, i - difficulty.HISTORY + 1): i + 1])
            assert abs(tier - target) <= abs(previous - target)                   # never away from where the scores point
            assert difficulty.tier_history(scores[: i + 1]) == tiers[: i + 1]     # appending sessions leaves earlier tiers alone
            previous = tier


def test_trend():
    assert difficulty.trend(2, 3) == "up" and difficulty.trend(4, 3) == "down" and difficulty.trend(3, 3) == "same"


# ── The level the next session gets (endpoint) ────────────────────────────────

def test_the_endpoint_requires_auth(client):
    assert client.get("/api/practice/difficulty").status_code == 401


def test_a_new_learner_starts_at_the_default_level(client, user):
    body = level(client, user["headers"])
    assert body["mode"] == "auto" and body["tier"] == body["auto_tier"] == DEFAULT_DIFFICULTY
    assert body["label"] == DIFFICULTY_LEVELS[DEFAULT_DIFFICULTY]["label"] == body["auto_label"]
    assert body["example"] == DIFFICULTY_LEVELS[DEFAULT_DIFFICULTY]["example"]
    assert body["trend"] == "same" and body["recent_scores"] == [] and "adapts" in body["reason"]


def test_the_level_follows_recent_scores_and_says_why(client, user):
    history(user["user"]["id"], 85, 88)                                          # tiers 3, then 4
    body = level(client, user["headers"])
    assert (body["mode"], body["tier"], body["label"], body["trend"]) == ("auto", 4, "Upper-Intermediate", "up")
    assert body["recent_scores"] == [88, 85]                                      # newest first
    assert body["reason"] == "Based on your last 2 session scores: 88, 85."


def test_a_single_session_is_described_in_the_singular(client, user):
    history(user["user"]["id"], 70)
    assert level(client, user["headers"])["reason"] == "Based on your last session score: 70."


def test_a_weak_session_after_strong_ones_steps_down_once(client, user):
    history(user["user"]["id"], 90, 90, 90, 20)
    body = level(client, user["headers"])
    assert (body["tier"], body["trend"]) == (4, "down") and body["recent_scores"] == [20, 90, 90]


def test_a_steady_level_shows_no_arrow(client, user):
    history(user["user"]["id"], 70, 72, 71)
    body = level(client, user["headers"])
    assert (body["tier"], body["trend"]) == (3, "same")


def test_sessions_count_in_the_order_they_ended_not_the_order_they_were_written(client, user):
    uid = user["user"]["id"]
    scored_session(uid, 20, ended_seconds_ago=86400)                              # the latest session, but written first
    scored_session(uid, 95, ended_seconds_ago=3 * 86400)
    scored_session(uid, 95, ended_seconds_ago=2 * 86400)
    body = level(client, user["headers"])
    assert (body["tier"], body["trend"]) == (3, "down")                           # 95, 95, 20: 3 -> 4 -> 3 (written order would read "up")


def test_sessions_without_a_score_are_ignored(client, user):
    uid = user["user"]["id"]
    scored_session(uid, 90, ended_seconds_ago=3 * 86400)
    scored_session(uid, None, ended_seconds_ago=2 * 86400)
    scored_session(uid, None, ended_seconds_ago=86400)
    body = level(client, user["headers"])
    assert body["tier"] == 3 and body["recent_scores"] == [90]


def test_other_learners_scores_do_not_count(client, user, make_user):
    history(make_user("someone.else@example.com")["user"]["id"], 95, 95, 95)
    assert level(client, user["headers"])["tier"] == DEFAULT_DIFFICULTY


def test_starting_sessions_without_finishing_them_does_not_ratchet_the_level(client, user, start_session, db):
    history(user["user"]["id"], 95)                                               # one strong session: the level is 3
    for _ in range(4):
        r = client.post("/api/conversation/start", headers=user["headers"])
        assert r.json()["difficulty"]["tier"] == 3
    assert level(client, user["headers"])["tier"] == 3
    assert [c.difficulty for c in db.query(Conversation).filter(Conversation.is_complete.is_(False))] == [3, 3, 3, 3]


# ── Pinning a level ───────────────────────────────────────────────────────────

def pin(client, headers, value):
    return client.patch("/api/auth/profile", headers=headers, json={"difficulty_override": value})


def test_a_pinned_level_wins_over_the_scores(client, user):
    history(user["user"]["id"], 30, 30, 30)
    r = pin(client, user["headers"], 5)
    assert r.status_code == 200 and r.json()["difficulty_override"] == 5
    body = level(client, user["headers"])
    assert (body["mode"], body["tier"], body["label"], body["trend"]) == ("manual", 5, "Advanced", "same")
    assert body["auto_tier"] == 1 and body["auto_label"] == "Beginner"            # what automatic would have chosen
    assert body["reason"] == "You chose this level."


def test_sending_null_goes_back_to_automatic(client, user):
    pin(client, user["headers"], 4)
    r = pin(client, user["headers"], None)
    assert r.status_code == 200 and r.json()["difficulty_override"] is None
    assert level(client, user["headers"])["mode"] == "auto"


def test_other_profile_edits_leave_a_pinned_level_alone(client, user):
    pin(client, user["headers"], 4)
    client.patch("/api/auth/profile", headers=user["headers"], json={"display_name": "New name"})
    assert client.get("/api/auth/me", headers=user["headers"]).json()["difficulty_override"] == 4


def test_the_pinned_level_is_part_of_the_signed_in_user(client, user):
    assert client.get("/api/auth/me", headers=user["headers"]).json()["difficulty_override"] is None
    pin(client, user["headers"], 2)
    assert client.get("/api/auth/me", headers=user["headers"]).json()["difficulty_override"] == 2


@pytest.mark.parametrize("bad", [0, 6, -1, 99, 2.5, "high", "3", True, [3]])
def test_a_made_up_level_is_refused_and_changes_nothing(client, user, bad):
    pin(client, user["headers"], 3)
    assert pin(client, user["headers"], bad).status_code == 422
    assert client.get("/api/auth/me", headers=user["headers"]).json()["difficulty_override"] == 3


def test_a_corrupt_stored_level_is_ignored(client, user, db):
    db.query(User).filter_by(id=user["user"]["id"]).update({"difficulty_override": 9})
    db.commit()
    body = level(client, user["headers"])
    assert body["mode"] == "auto" and body["tier"] == DEFAULT_DIFFICULTY


# ── The session uses it ───────────────────────────────────────────────────────

def test_a_new_session_records_and_reports_its_level(client, user, db):
    r = client.post("/api/conversation/start", headers=user["headers"])
    assert r.json()["difficulty"] == {"tier": DEFAULT_DIFFICULTY, "label": "Elementary"}
    assert db.get(Conversation, r.json()["conversation_id"]).difficulty == DEFAULT_DIFFICULTY


def test_a_new_session_uses_the_level_the_scores_call_for(client, user):
    history(user["user"]["id"], 85, 88)
    assert client.post("/api/conversation/start", headers=user["headers"]).json()["difficulty"] == {"tier": 4, "label": "Upper-Intermediate"}


def test_a_new_session_uses_the_pinned_level(client, user):
    pin(client, user["headers"], 1)
    assert client.post("/api/conversation/start", headers=user["headers"]).json()["difficulty"] == {"tier": 1, "label": "Beginner"}


@pytest.mark.parametrize("tier", sorted(DIFFICULTY_LEVELS))
def test_the_coach_is_told_the_sessions_level(user, client, start_session, ai, post_turn, tier):
    pin(client, user["headers"], tier)
    post_turn(user["headers"], start_session(user["headers"]))
    system = ai.llm_calls[0][0]["content"]
    assert f"DIFFICULTY ({DIFFICULTY_LEVELS[tier]['label']}): {DIFFICULTY_LEVELS[tier]['prompt']}" in system
    assert system.count("DIFFICULTY (") == 1


def test_the_level_is_fixed_for_the_whole_session(user, client, start_session, ai, post_turn):
    cid = start_session(user["headers"])                                          # started at the default level
    pin(client, user["headers"], 5)                                               # changed their mind mid-session
    post_turn(user["headers"], cid)
    assert "DIFFICULTY (Elementary)" in ai.llm_calls[0][0]["content"]
    assert "DIFFICULTY (Advanced)" not in ai.llm_calls[0][0]["content"]
    assert client.post("/api/conversation/start", headers=user["headers"]).json()["difficulty"]["tier"] == 5   # but the next one has it


def test_a_session_from_before_levels_existed_gets_no_difficulty_instruction(user, start_session, ai, post_turn, db):
    cid = start_session(user["headers"])
    db.query(Conversation).filter_by(id=cid).update({"difficulty": None})
    db.commit()
    post_turn(user["headers"], cid)
    assert "DIFFICULTY (" not in ai.llm_calls[0][0]["content"]


def test_the_level_and_a_focus_work_together(user, start_session, ai, post_turn):
    post_turn(user["headers"], start_session(user["headers"], focus="grammar:past_tense"))
    system = ai.llm_calls[0][0]["content"]
    assert "DIFFICULTY (" in system and "HIDDEN PRACTICE FOCUS" in system


def test_history_shows_the_level_each_session_ran_at(client, user, start_session, db):
    pin(client, user["headers"], 4)
    cid = start_session(user["headers"])
    listed = client.get("/api/history/sessions", headers=user["headers"]).json()["sessions"][0]
    detail = client.get(f"/api/history/sessions/{cid}", headers=user["headers"]).json()
    assert listed["difficulty"] == detail["difficulty"] == {"tier": 4, "label": "Upper-Intermediate"}


def test_history_has_no_level_for_sessions_from_before_levels_existed(client, user, start_session, db):
    cid = start_session(user["headers"])
    db.query(Conversation).filter_by(id=cid).update({"difficulty": None})
    db.commit()
    assert client.get(f"/api/history/sessions/{cid}", headers=user["headers"]).json()["difficulty"] is None
    assert client.get("/api/history/sessions", headers=user["headers"]).json()["sessions"][0]["difficulty"] is None


# ── The prompt builder ────────────────────────────────────────────────────────

@pytest.mark.parametrize("tier", sorted(DIFFICULTY_LEVELS))
def test_every_tier_has_its_own_instruction(tier):
    info = DIFFICULTY_LEVELS[tier]
    assert info["label"] and info["prompt"] and info["example"]
    assert f"DIFFICULTY ({info['label']}): {info['prompt']}" in build_system_prompt(difficulty=tier)


@pytest.mark.parametrize("bad", [None, 0, 6, "3"])
def test_no_or_unknown_difficulty_adds_no_instruction(bad):
    assert "DIFFICULTY" not in build_system_prompt(difficulty=bad)


def test_the_tiers_are_ordered_from_easy_to_hard():
    assert sorted(DIFFICULTY_LEVELS) == [1, 2, 3, 4, 5]
    assert [DIFFICULTY_LEVELS[t]["label"] for t in range(1, 6)] == ["Beginner", "Elementary", "Intermediate", "Upper-Intermediate", "Advanced"]
