"""Fluency analysis: the pure maths (services/fluency.py) and how it flows through the API."""
import json

import pytest

from backend.database import SessionLocal
from backend.models.metrics import FluencyEvent, FluencyScore
from backend.services import fluency, speech_metrics


def speech(spec, step=0.45, dur=0.35, start=0.0):
    """
    Builds a word list from a string, e.g. "I went home | 1.2 | and slept".
    Words are `dur` long and start `step` apart; "| 1.2 |" inserts a 1.2 s gap.
    """
    words, t = [], start
    for part in spec.split():
        if part.startswith("|"):
            continue
        try:
            t += float(part) - (step - dur)      # a gap token like "1.2": silence of that length
            continue
        except ValueError:
            pass
        words.append({"word": part, "start": round(t, 3), "end": round(t + dur, 3), "probability": 0.95})
        t += step
    return words


def kinds(metrics):
    return [e["kind"] for e in metrics.events]


# ── Rate ──────────────────────────────────────────────────────────────────────

def test_steady_speech_scores_full_marks():
    m = fluency.analyse(speech("I went to the shop yesterday and I bought some fresh bread for my family because we were hungry"))
    assert m.pause_count == 0 and m.filler_count == 0 and m.repetition_count == 0
    assert 120 <= m.wpm <= 150
    assert m.score == 100


def test_wpm_is_measured_over_the_time_spent_speaking_not_the_clip_length():
    words = speech("one two three four five six", step=0.5, dur=0.4, start=3.0)   # silence before the first word
    m = fluency.analyse(words)
    assert m.speech_seconds == pytest.approx(2.9, abs=0.01)
    assert m.wpm == pytest.approx(6 / 2.9 * 60, abs=0.2)


def test_rate_is_withheld_when_there_is_too_little_speech():
    assert fluency.analyse(speech("hello there")).wpm is None            # under 3 words
    assert fluency.analyse(speech("a b c", step=0.1, dur=0.08)).wpm is None  # under a second


def test_articulation_rate_excludes_pauses():
    m = fluency.analyse(speech("I think that 1.5 it was really very good indeed"))
    assert m.pause_count == 1 and m.articulation_wpm > m.wpm


# ── Pauses ────────────────────────────────────────────────────────────────────

def test_a_pause_in_the_middle_of_a_thought_counts():
    m = fluency.analyse(speech("I went to the 0.9 mall yesterday"))
    assert m.pause_count == 1 and m.long_pause_count == 0
    pause = next(e for e in m.events if e["kind"] == "pause")
    assert pause["text"] == "0.9s" and pause["end"] - pause["start"] == pytest.approx(0.9, abs=0.01)
    assert m.total_pause_seconds == pytest.approx(0.9, abs=0.01) and m.longest_pause_seconds == pytest.approx(0.9, abs=0.01)


def test_short_gaps_are_not_pauses():
    assert fluency.analyse(speech("I went to the 0.4 mall yesterday")).pause_count == 0


def test_a_long_pause_is_flagged_and_also_counts_as_a_pause():
    m = fluency.analyse(speech("I went to the 1.8 mall yesterday"))
    assert (m.pause_count, m.long_pause_count) == (1, 1) and "long_pause" in kinds(m)


def test_a_breath_between_sentences_is_not_hesitation():
    m = fluency.analyse(speech("I went to the mall. 1.4 It was crowded and loud"))
    assert m.pause_count == 0
    m = fluency.analyse(speech("Did you go? 1.4 I did indeed go there yesterday"))
    assert m.pause_count == 0


def test_a_short_pause_after_a_comma_is_normal_phrasing_but_a_long_one_is_not():
    assert fluency.analyse(speech("Well, 0.8 I think it was fine yesterday")).pause_count == 0
    assert fluency.analyse(speech("Well, 1.3 I think it was fine yesterday")).pause_count == 1


# ── Fillers ───────────────────────────────────────────────────────────────────

def test_hesitation_sounds_are_counted_and_normalised():
    m = fluency.analyse(speech("Well, Umm, I think, uhh, it was um fine erm yes"), hesitations_tracked=True)
    assert m.filler_breakdown == {"um": 2, "uh": 1, "er": 1}
    assert m.filler_count == 4 and m.hesitations_tracked is True


def test_hesitations_are_not_words():
    assert fluency.analyse(speech("um hello there my friend")).word_count == 4


def test_like_is_a_filler_only_when_set_off_by_commas():
    assert fluency.analyse(speech("I like pizza and I like pasta too")).filler_count == 0
    m = fluency.analyse(speech("The trip was, like, really good"))
    assert m.filler_breakdown == {"like": 1}


def test_discourse_fillers_need_commas_too():
    assert fluency.analyse(speech("Do you know where the station is")).filler_count == 0
    assert fluency.analyse(speech("What kind of music do you like")).filler_count == 0
    m = fluency.analyse(speech("It was, you know, a long day and, sort of, tiring"))
    assert m.filler_breakdown == {"you know": 1, "sort of": 1}


def test_basically_is_always_a_filler():
    assert fluency.analyse(speech("It is basically a small shop")).filler_breakdown == {"basically": 1}


def test_breakdown_is_ordered_by_frequency():
    m = fluency.analyse(speech("um I uh um went um home"))
    assert list(m.filler_breakdown) == ["um", "uh"]


def test_filler_events_carry_their_timestamps():
    m = fluency.analyse(speech("so um we went home"))
    filler = next(e for e in m.events if e["kind"] == "filler")
    assert filler["text"] == "um" and filler["start"] == pytest.approx(0.45, abs=0.01)


# ── Repetitions ───────────────────────────────────────────────────────────────

def test_stuttered_repeats_count_but_legitimate_doubles_do_not():
    assert fluency.analyse(speech("I I went to the the shop")).repetition_count == 2
    assert fluency.analyse(speech("He said that that was fine and had had enough")).repetition_count == 0
    assert fluency.analyse(speech("it was very very good")).repetition_count == 0


def test_a_repeated_hesitation_is_two_fillers_not_a_repetition():
    m = fluency.analyse(speech("so um um we went"))
    assert m.filler_count == 2 and m.repetition_count == 0


# ── Score ─────────────────────────────────────────────────────────────────────

def test_the_score_starts_at_100_and_deductions_are_capped():
    assert fluency.compute_score(130, 0, 0, 0, 0, 20) == 100
    assert fluency.compute_score(130, 100, 0, 0, 0, 20) == 80       # pauses cap at -20
    assert fluency.compute_score(130, 0, 100, 0, 0, 20) == 88       # long pauses cap at -12
    assert fluency.compute_score(130, 0, 0, 100, 0, 20) == 75       # fillers cap at -25
    assert fluency.compute_score(130, 0, 0, 0, 100, 20) == 90       # repetitions cap at -10


def test_the_score_penalises_rate_at_both_extremes_and_tiny_answers():
    assert fluency.compute_score(50, 0, 0, 0, 0, 20) == 75
    assert fluency.compute_score(70, 0, 0, 0, 0, 20) == 80
    assert fluency.compute_score(90, 0, 0, 0, 0, 20) == 92
    assert fluency.compute_score(190, 0, 0, 0, 0, 20) == 97
    assert fluency.compute_score(230, 0, 0, 0, 0, 20) == 90
    assert fluency.compute_score(None, 0, 0, 0, 0, 5) == 85        # very short answer


def test_the_score_never_leaves_0_100():
    assert fluency.compute_score(10, 99, 99, 99, 99, 1) >= 0
    assert fluency.compute_score(130, 0, 0, 0, 0, 50) <= 100


def test_a_messy_turn_scores_lower_than_a_clean_one():
    clean = fluency.analyse(speech("I went to the shop yesterday and I bought some fresh bread for my family tonight"))
    messy = fluency.analyse(speech("I um went 1.8 to the the shop uh yesterday 1.2 and I bought some bread"), hesitations_tracked=True)
    assert messy.score < clean.score - 20


# ── Edge cases and shape ──────────────────────────────────────────────────────

def test_no_words_is_handled():
    m = fluency.analyse([])
    assert (m.word_count, m.wpm, m.pause_count, m.filler_count) == (0, None, 0, 0)
    assert 0 <= m.score <= 100


def test_garbage_tokens_are_ignored():
    m = fluency.analyse([{"word": "—", "start": 0, "end": 0.2}, {"word": "", "start": 0.2, "end": 0.3}] + speech("hello there my friend"))
    assert m.word_count == 4


def test_everything_is_json_serialisable_with_plain_types():
    m = fluency.analyse(speech("so um 1.6 we went, like, home"), hesitations_tracked=True)
    d = m.to_dict()
    json.dumps(d)
    assert d["events"] == sorted(d["events"], key=lambda e: (e["start"], e["end"]))
    assert all(type(v) in (int, float, str, bool, type(None), dict, list) for v in d.values())


# ── Through the API ───────────────────────────────────────────────────────────

SPOKEN = "Well um I went to the 1.3 mall yesterday and I bought some, like, clothes for my friend"


def test_a_turn_stores_fluency_and_sends_a_metrics_event(user, start_session, ai, post_turn, db):
    ai.words = speech(SPOKEN)
    ai.transcript = "Well um I went to the mall yesterday and I bought some, like, clothes for my friend"
    _, events = post_turn(user["headers"], start_session(user["headers"]))

    types = [e["type"] for e in events]
    assert types[:2] == ["transcript", "metrics"]                   # metrics arrive right after the transcript
    metrics_event = events[1]
    assert metrics_event["message_id"] == events[0]["message_id"]
    f = metrics_event["fluency"]
    assert f["pause_count"] == 1 and f["filler_count"] == 2 and f["word_count"] > 10
    assert f["filler_breakdown"] == {"um": 1, "like": 1}
    assert f["hesitations_tracked"] is False                        # local provider: it can't hear "um"

    row = db.query(FluencyScore).one()
    assert row.message_id == events[0]["message_id"] and row.score == f["score"]
    assert row.filler_breakdown == {"um": 1, "like": 1}
    assert sorted(e.kind for e in db.query(FluencyEvent).all()) == ["filler", "filler", "pause"]


def test_hesitations_tracked_follows_the_stt_provider(user, start_session, ai, post_turn, monkeypatch):
    from backend.services import stt

    monkeypatch.setattr(stt, "STT_PROVIDER", "groq")
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert events[1]["fluency"]["hesitations_tracked"] is True


def test_a_metrics_bug_never_costs_the_learner_their_turn(user, start_session, ai, post_turn, monkeypatch, db):
    from backend.models.core import Message

    monkeypatch.setattr(fluency, "analyse", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bug")))
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert [e["type"] for e in events][:2] == ["transcript", "metrics"] and events[1]["fluency"] is None
    assert events[-1]["type"] == "done" and events[-1]["full_reply"]
    assert db.query(Message).filter_by(role="user").count() == 1 and db.query(FluencyScore).count() == 0


def test_failing_to_save_metrics_still_saves_the_message(user, start_session, ai, post_turn, monkeypatch, db):
    from backend.models.core import Message

    def broken_save(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(speech_metrics, "save", broken_save)
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert events[-1]["type"] == "done"
    assert db.query(Message).filter_by(role="user").count() == 1 and db.query(FluencyScore).count() == 0


def test_history_detail_includes_fluency_per_turn_and_an_average(client, user, start_session, ai, post_turn, wait_for_analysis):
    cid = start_session(user["headers"])
    ai.words = speech(SPOKEN)
    ai.transcript = "Well um I went to the mall yesterday and I bought some, like, clothes for my friend"
    post_turn(user["headers"], cid)
    ai.words = speech("I went to the shop yesterday and I bought some fresh bread for my family tonight")
    ai.transcript = "I went to the shop yesterday and I bought some fresh bread for my family tonight"
    post_turn(user["headers"], cid)
    wait_for_analysis(cid)

    d = client.get(f"/api/history/sessions/{cid}", headers=user["headers"]).json()
    user_turns = [m for m in d["messages"] if m["role"] == "user"]
    assert [bool(m["fluency"]) for m in d["messages"]] == [True, False, True, False]   # only the user's turns have it
    first, second = user_turns[0]["fluency"], user_turns[1]["fluency"]
    assert second["score"] > first["score"]
    assert {e["kind"] for e in first["events"]} == {"pause", "filler"}
    assert d["avg_fluency"] == round((first["score"] + second["score"]) / 2)

    listing = client.get("/api/history/sessions", headers=user["headers"]).json()["sessions"][0]
    assert listing["avg_fluency"] == d["avg_fluency"]


def test_sessions_without_metrics_report_null(client, user, start_session):
    cid = start_session(user["headers"])
    assert client.get(f"/api/history/sessions/{cid}", headers=user["headers"]).json()["avg_fluency"] is None
    assert client.get("/api/history/sessions", headers=user["headers"]).json()["sessions"][0]["avg_fluency"] is None


def test_deleting_the_account_removes_the_metrics_too(client, user, start_session, ai, post_turn, db):
    from backend.tests.conftest import PASSWORD

    ai.words = speech(SPOKEN)
    post_turn(user["headers"], start_session(user["headers"]))
    assert db.query(FluencyScore).count() == 1 and db.query(FluencyEvent).count() >= 1
    r = client.request("DELETE", "/api/auth/account", headers=user["headers"], json={"confirm_email": user["email"], "password": PASSWORD})
    assert r.status_code == 204
    db.expire_all()
    assert db.query(FluencyScore).count() == 0 and db.query(FluencyEvent).count() == 0
