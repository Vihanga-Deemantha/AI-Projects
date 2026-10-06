"""Session reports: generation, the end-of-session flow, and the report endpoint."""
import threading
from datetime import datetime, timedelta, timezone

import pytest

from backend.database import SessionLocal
from backend.models.core import Conversation, Correction, Message
from backend.models.reports import SessionReport
from backend.services import reports


def finished_session(user_id: str, turns=2, status="done", ended_seconds_ago=3600, corrections=(), words_per_turn=12) -> str:
    """A completed session built straight in the database (as old sessions are)."""
    ended = datetime.now(timezone.utc) - timedelta(seconds=ended_seconds_ago)
    with SessionLocal() as s:
        c = Conversation(user_id=user_id, started_at=ended - timedelta(seconds=90), ended_at=ended, is_complete=True)
        s.add(c)
        s.flush()
        first = None
        for i in range(turns):
            m = Message(conversation_id=c.id, role="user", content=" ".join(["word"] * words_per_turn), analysis_status=status,
                        created_at=ended - timedelta(seconds=80 - i))
            s.add(m)
            s.flush()
            first = first or m.id
        for kw in corrections:
            s.add(Correction(message_id=first, user_id=user_id, conversation_id=c.id,
                             **{**dict(category="grammar", subtype="past_tense", original="I go", correction="I went",
                                       explanation="x", is_error=True, is_positive=False, severity="medium"), **kw}))
        s.commit()
        return c.id


def mistake(**kw):
    return kw


# ── Through the real flow ─────────────────────────────────────────────────────

def test_ending_a_session_builds_its_report(client, user, start_session, ai, post_turn, wait_for_analysis, db):
    cid = start_session(user["headers"])
    ai.transcript = "Yesterday I go to the mall and it was a piece of cake to find parking."
    ai.analysis_payload = {"corrections": [
        {"category": "grammar", "subtype": "past_tense", "original": "I go to the mall", "correction": "I went to the mall",
         "explanation": "Use the past.", "is_error": True, "severity": "high"},
        {"category": "naturalness", "subtype": "idiom_used", "original": "a piece of cake", "correction": "", "explanation": "Very easy.",
         "is_error": False, "is_positive": True},
    ]}
    post_turn(user["headers"], cid)
    assert client.post(f"/api/conversation/{cid}/end", headers=user["headers"]).status_code == 200

    r = client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"])
    assert r.status_code == 200 and r.json()["status"] == "ready"
    report = r.json()["report"]
    assert report["scores"]["overall"] is not None and report["scores"]["fluency"] is not None
    assert report["facts"]["turns"] == 1 and report["facts"]["mistakes"] == 1 and report["facts"]["praise"] == 1
    assert report["top_errors"][0]["label"] == "Past tense"
    assert any("idiom" in s.lower() for s in report["strengths"])
    assert report["summary"] and "confidence" in report["summary"]

    db.expire_all()
    assert db.get(Conversation, cid).overall_score == report["scores"]["overall"]
    listing = client.get("/api/history/sessions", headers=user["headers"]).json()["sessions"][0]
    assert listing["overall_score"] == report["scores"]["overall"]


def test_the_report_waits_for_the_last_turns_analysis(client, user, start_session, ai, post_turn):
    """The final turn's mistakes must be in the score even though analysis was still running at 'End'."""
    ai.analysis_gate = threading.Event()
    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)                                   # analysis is now blocked on the gate
    threading.Timer(1.0, ai.analysis_gate.set).start()                # ...and finishes a second after the session ends

    client.post(f"/api/conversation/{cid}/end", headers=user["headers"])   # background report waits for it
    report = client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"]).json()["report"]
    assert report["facts"]["mistakes"] == 1                           # the mistake the gated analysis found


def test_reports_are_created_once_and_end_is_idempotent(client, user, start_session, ai, post_turn, db):
    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)
    client.post(f"/api/conversation/{cid}/end", headers=user["headers"])
    client.post(f"/api/conversation/{cid}/end", headers=user["headers"])
    first = client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"]).json()["report"]
    second = client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"]).json()["report"]
    assert first["id"] == second["id"] and db.query(SessionReport).count() == 1


# ── Endpoint states ───────────────────────────────────────────────────────────

def test_a_running_session_has_no_report_yet(client, user, start_session):
    cid = start_session(user["headers"])
    assert client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"]).status_code == 409


def test_a_session_with_no_turns_has_nothing_to_report(client, user, start_session):
    cid = start_session(user["headers"])
    client.post(f"/api/conversation/{cid}/end", headers=user["headers"])
    assert client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"]).status_code == 404


def test_a_just_ended_session_still_being_analysed_answers_202(client, user):
    cid = finished_session(user["user"]["id"], status="pending", ended_seconds_ago=3)
    r = client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"])
    assert r.status_code == 202 and r.json() == {"status": "pending"}


def test_stale_pending_turns_do_not_hold_a_report_up_forever(client, user, db):
    cid = finished_session(user["user"]["id"], status="pending", ended_seconds_ago=3)
    db.query(Message).filter_by(conversation_id=cid).update({"created_at": datetime.now(timezone.utc) - timedelta(minutes=10)})
    db.commit()
    assert client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"]).status_code == 200


def test_old_sessions_are_reported_on_when_first_opened(client, user, db):
    cid = finished_session(user["user"]["id"], corrections=[mistake(), mistake(subtype="articles", original="a apple", correction="an apple")])
    assert db.query(SessionReport).count() == 0
    r = client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"])
    assert r.status_code == 200 and r.json()["report"]["facts"]["mistakes"] == 2
    assert db.query(SessionReport).count() == 1


def test_reports_belong_to_their_owner(client, user, make_user):
    cid = finished_session(user["user"]["id"])
    other = make_user("other@example.com")
    assert client.get(f"/api/history/sessions/{cid}/report", headers=other["headers"]).status_code == 404
    assert client.get(f"/api/history/sessions/{cid}/report").status_code == 401
    assert client.get("/api/history/sessions/nope/report", headers=user["headers"]).status_code == 404


# ── Content ───────────────────────────────────────────────────────────────────

def test_a_session_where_no_analysis_finished_does_not_claim_perfect_grammar(client, user):
    cid = finished_session(user["user"]["id"], status="failed")
    scores = client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"]).json()["report"]["scores"]
    assert scores["grammar"] is None and scores["vocabulary"] is None and scores["naturalness"] is None
    assert scores["overall"] is None                                  # nothing at all to base a number on


def test_words_from_unanalysed_turns_do_not_dilute_the_mistake_density(client, user):
    """A 500-word turn whose analysis failed says nothing about mistakes, so it must not make them look rarer."""
    cid = finished_session(user["user"]["id"], turns=1, words_per_turn=20, corrections=[mistake()])
    with SessionLocal() as s:
        s.add(Message(conversation_id=cid, role="user", content=" ".join(["word"] * 500), analysis_status="failed"))
        s.commit()
    scores = client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"]).json()["report"]["scores"]
    assert scores["grammar"] == 80          # 1 mistake over the 20 ANALYSED words = 5 per 100 -> 100 - 4*5 (diluted over 520 words it would be 99)


def test_the_summary_is_optional(client, user, ai):
    ai.summary = None                                                 # the LLM is down
    cid = finished_session(user["user"]["id"])
    r = client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"])
    assert r.status_code == 200 and r.json()["report"]["summary"] is None


def test_a_useless_summary_is_dropped(client, user, ai):
    ai.summary = "Ok."
    cid = finished_session(user["user"]["id"])
    assert client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"]).json()["report"]["summary"] is None


def test_the_summary_is_written_from_the_computed_facts(client, user, ai):
    cid = finished_session(user["user"]["id"], corrections=[mistake()])
    client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"])
    sent = ai.summary_calls[0][1]["content"]
    assert "past tense" in sent.lower() and "scores" in sent


def test_no_summary_is_requested_when_there_is_nothing_to_score(client, user, ai):
    cid = finished_session(user["user"]["id"], status="failed")
    client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"])
    assert ai.summary_calls == []


def test_the_report_records_which_scoring_formulas_produced_it(client, user):
    from backend.services import scoring

    cid = finished_session(user["user"]["id"])
    assert client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"]).json()["report"]["scoring_version"] == scoring.SCORING_VERSION


# ── Robustness ────────────────────────────────────────────────────────────────

def test_losing_the_generation_race_reads_the_winners_report(user, db):
    cid = finished_session(user["user"]["id"])
    first = reports.generate_report(cid)
    second = reports.generate_report(cid)
    assert first["id"] == second["id"]
    assert db.query(SessionReport).count() == 1


def test_a_report_written_by_a_concurrent_writer_is_returned_not_duplicated(user, db, monkeypatch):
    cid = finished_session(user["user"]["id"])
    winner = reports.generate_report(cid)

    real_get, calls = reports.get_report, {"n": 0}

    def get_report_that_misses_once(db_, conversation_id):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_get(db_, conversation_id)   # the other writer hadn't committed yet

    monkeypatch.setattr(reports, "get_report", get_report_that_misses_once)
    again = reports.generate_report(cid)                 # inserts, hits the unique key, falls back to the winner's row
    assert again["id"] == winner["id"] and db.query(SessionReport).count() == 1


def test_the_safe_entry_point_never_raises(user, monkeypatch):
    monkeypatch.setattr(reports, "generate_report", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    reports.generate_report_safely("whatever")                         # must not raise inside a background task


def test_waiting_for_analysis_returns_immediately_when_nothing_is_pending(user):
    cid = finished_session(user["user"]["id"])
    assert reports.wait_for_analysis(cid, timeout=0.1) is True


def test_waiting_for_analysis_gives_up_at_the_timeout(user):
    cid = finished_session(user["user"]["id"], status="pending", ended_seconds_ago=3)
    assert reports.wait_for_analysis(cid, timeout=0.6) is False


def test_deleting_the_account_removes_the_reports(client, user, db):
    from backend.tests.conftest import PASSWORD

    cid = finished_session(user["user"]["id"])
    client.get(f"/api/history/sessions/{cid}/report", headers=user["headers"])
    assert db.query(SessionReport).count() == 1
    client.request("DELETE", "/api/auth/account", headers=user["headers"], json={"confirm_email": user["email"], "password": PASSWORD})
    db.expire_all()
    assert db.query(SessionReport).count() == 0
