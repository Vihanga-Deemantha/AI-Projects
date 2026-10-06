"""Starting/ending sessions and the streaming voice loop."""
import threading

import pytest

from backend.database import SessionLocal
from backend.models.core import Conversation, Message
from backend.services import stt
from backend.tests.conftest import bearer

LONG_REPLY = [
    "I think that is a really great idea for your next holiday trip. ",
    "Where would you like to go first this summer?",
]


def _types(events):
    return [e["type"] for e in events]


# ── Start / end ───────────────────────────────────────────────────────────────

def test_start_requires_auth(client):
    assert client.post("/api/conversation/start", data={}).status_code == 401


def test_start_defaults_and_ownership(client, user, db):
    r = client.post("/api/conversation/start", headers=user["headers"], data={})
    assert r.status_code == 200
    body = r.json()
    assert (body["scenario"], body["style"], body["voice"]) == ("casual", "standard", "amy")
    assert body["user_id"] == user["user"]["id"]
    assert db.query(Conversation).one().user_id == user["user"]["id"]


@pytest.mark.parametrize("field", ["voice", "style", "scenario"])
def test_start_rejects_unknown_ids(client, user, field):
    assert client.post("/api/conversation/start", headers=user["headers"], data={field: "nope"}).status_code == 400


def test_start_rejects_a_voice_that_isnt_installed(client, user, ai, monkeypatch):
    from backend.services import tts

    monkeypatch.setattr(tts, "voice_available", lambda v: v != "ryan")
    assert client.post("/api/conversation/start", headers=user["headers"], data={"voice": "ryan"}).status_code == 400
    assert client.post("/api/conversation/start", headers=user["headers"], data={"voice": "amy"}).status_code == 200


def test_end_is_idempotent_and_owned(client, user, make_user, start_session):
    cid = start_session(user["headers"])
    first = client.post(f"/api/conversation/{cid}/end", headers=user["headers"]).json()
    second = client.post(f"/api/conversation/{cid}/end", headers=user["headers"]).json()
    assert first["is_complete"] is True and first["ended_at"] == second["ended_at"]

    other = make_user("other@example.com")
    assert client.post(f"/api/conversation/{cid}/end", headers=other["headers"]).status_code == 404


# ── The voice loop ────────────────────────────────────────────────────────────

def test_a_turn_streams_transcript_then_audio_then_done(user, start_session, ai, post_turn, db):
    cid = start_session(user["headers"])
    r, events = post_turn(user["headers"], cid)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")

    assert _types(events)[0] == "transcript" and _types(events)[-1] == "done"
    assert "audio_chunk" in _types(events) and "error" not in _types(events)
    transcript = events[0]
    assert transcript["text"] == ai.transcript and transcript["message_id"]

    done = events[-1]
    assert done["full_reply"] == "That sounds like a busy day! What did you buy?"
    for key in ("stt_ms", "llm_ttfs_ms", "first_audio_ms", "total_ms"):
        assert done["timings"][key] is not None and done["timings"][key] >= 0

    rows = db.query(Message).filter_by(conversation_id=cid).order_by(Message.created_at).all()
    assert [m.role for m in rows] == ["user", "assistant"]
    assert rows[0].content == ai.transcript and rows[1].content == done["full_reply"]
    assert rows[0].id == transcript["message_id"]


def test_long_replies_are_split_into_sentence_chunks(user, start_session, ai, post_turn):
    ai.reply_tokens = LONG_REPLY
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    chunks = [e for e in events if e["type"] == "audio_chunk"]
    assert [c["index"] for c in chunks] == [0, 1]
    assert chunks[0]["text"].startswith("I think that") and chunks[1]["text"].startswith("Where would")
    assert all(c["data"] for c in chunks)


def test_a_short_opening_sentence_is_spoken_straight_away(user, start_session, ai, post_turn):
    """The learner waits in silence for the first chunk, so a brief opener must not idle for more text."""
    ai.reply_tokens = ["Sounds like a busy day! ", "I hope you found something really nice to wear for the trip. ", "Tell me more."]
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    chunks = [e["text"] for e in events if e["type"] == "audio_chunk"]
    assert chunks[0] == "Sounds like a busy day!"
    assert chunks[1].startswith("I hope you found something")      # later chunks are still sentence-sized


def test_the_conversation_voice_is_used_for_tts(user, start_session, ai, post_turn):
    post_turn(user["headers"], start_session(user["headers"], voice="alan"))
    assert {voice for _, voice in ai.tts_calls} == {"alan"}


def test_raw_stt_word_timings_are_stored_as_real_json(user, start_session, ai, post_turn, db):
    import json

    post_turn(user["headers"], start_session(user["headers"]))
    stored = db.query(Message).filter_by(role="user").one()
    words = json.loads(stored.word_timestamps_json)   # used to be Python repr with np.float64(...)
    assert words[0]["word"] == "Yesterday" and isinstance(words[0]["start"], float)
    assert stored.audio_duration_seconds == ai.duration and stored.whisper_avg_logprob == ai.avg_logprob


# ── The coach must see the LATEST turn (regression: oldest-10 bug) ────────────

def test_the_latest_user_turn_always_reaches_the_llm(user, start_session, ai, post_turn):
    cid = start_session(user["headers"])
    for i in range(14):
        ai.transcript = f"this is my spoken turn number {i}"
        post_turn(user["headers"], cid)
    last_call = ai.llm_calls[-1]
    assert last_call[-1] == {"role": "user", "content": "this is my spoken turn number 13"}


def test_the_llm_context_is_a_sliding_window_of_recent_messages(user, start_session, ai, post_turn):
    from backend.config import LLM_CONTEXT_MESSAGES

    cid = start_session(user["headers"])
    for i in range(14):
        ai.transcript = f"this is my spoken turn number {i}"
        post_turn(user["headers"], cid)
    messages = ai.llm_calls[-1]
    assert messages[0]["role"] == "system"
    assert len(messages) == 1 + LLM_CONTEXT_MESSAGES
    contents = [m["content"] for m in messages[1:]]
    assert "this is my spoken turn number 0" not in contents          # oldest turns fall out of the window
    assert "this is my spoken turn number 12" in contents             # recent history is kept
    roles = [m["role"] for m in messages[1:]]
    assert roles[-1] == "user"


def test_the_system_prompt_reflects_scenario_and_style(user, start_session, ai, post_turn):
    post_turn(user["headers"], start_session(user["headers"], scenario="interview", style="irish"))
    system = ai.llm_calls[0][0]["content"]
    assert "interviewer" in system.lower() and "irish" in system.lower()


# ── Failure paths: always a clean error + done, never a hung stream ──────────

def test_audio_decode_errors_are_reported_without_leaking_internals(user, start_session, ai, post_turn):
    ai.stt_error = stt.AudioDecodeError("Could not process that recording — try again.")
    r, events = post_turn(user["headers"], start_session(user["headers"]))
    assert _types(events) == ["error", "done"]
    assert "Could not process that recording" in events[0]["message"]


def test_unexpected_stt_failures_are_generic(user, start_session, ai, post_turn):
    ai.stt_error = RuntimeError("ffmpeg exploded at /tmp/secret/path")
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert _types(events) == ["error", "done"] and "ffmpeg" not in events[0]["message"] and "/tmp" not in events[0]["message"]


def test_stt_provider_outage_is_reported(user, start_session, ai, post_turn):
    ai.stt_error = stt.STTUnavailableError("Speech recognition is unavailable right now. Please try again in a moment.")
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert "unavailable" in events[0]["message"]


def test_silence_is_reported_and_nothing_is_saved(user, start_session, ai, post_turn, db):
    ai.transcript = ""
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert _types(events) == ["error", "done"] and events[0]["message"] == "No speech detected"
    assert db.query(Message).count() == 0 and ai.llm_calls == []


def test_empty_upload_never_reaches_stt(user, start_session, ai, post_turn):
    _, events = post_turn(user["headers"], start_session(user["headers"]), audio=b"")
    assert _types(events) == ["error", "done"] and ai.stt_calls == 0


def test_recordings_longer_than_the_cap_are_rejected_before_the_llm(user, start_session, ai, post_turn):
    ai.duration = 9999
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert "too long" in events[0]["message"] and ai.llm_calls == []


def test_llm_failure_keeps_the_users_turn_and_ends_cleanly(user, start_session, ai, post_turn, db):
    ai.llm_error = RuntimeError("provider 503 secret-details")
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert _types(events)[0] == "transcript" and _types(events)[-2:] == ["error", "done"]
    assert "secret-details" not in events[-2]["message"]
    assert [m.role for m in db.query(Message).all()] == ["user"]


def test_llm_failure_mid_reply_saves_what_was_already_spoken(user, start_session, ai, post_turn, db):
    ai.reply_tokens = LONG_REPLY
    ai.llm_error, ai.llm_error_after = RuntimeError("dropped"), 1   # first sentence spoken, then the stream dies
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert _types(events).count("audio_chunk") == 1 and _types(events)[-2:] == ["error", "done"]
    assistant = db.query(Message).filter_by(role="assistant").one()
    assert assistant.content.startswith("I think that is a really great idea")


def test_empty_llm_reply_is_an_error_not_silence(user, start_session, ai, post_turn, db):
    ai.reply_tokens = []
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert _types(events)[-2:] == ["error", "done"] and "didn't reply" in events[-2]["message"]
    assert db.query(Message).filter_by(role="assistant").count() == 0


def test_tts_failure_warns_but_the_reply_text_survives(user, start_session, ai, post_turn, db):
    ai.tts_error = RuntimeError("onnx blew up")
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert "warning" in _types(events) and "audio_chunk" not in _types(events)
    assert events[-1]["type"] == "done" and events[-1]["full_reply"]
    assert db.query(Message).filter_by(role="assistant").one().content == events[-1]["full_reply"]


# ── Access control ────────────────────────────────────────────────────────────

def test_turns_require_auth(client, user, start_session, ai):
    cid = start_session(user["headers"])
    r = client.post("/api/conversation/message-stream", data={"conversation_id": cid}, files={"audio_file": ("a.webm", b"x", "audio/webm")})
    assert r.status_code == 401


def test_cannot_post_into_someone_elses_conversation(user, make_user, start_session, ai, post_turn):
    cid = start_session(user["headers"])
    r, _ = post_turn(make_user("other@example.com")["headers"], cid)
    assert r.status_code == 404 and ai.stt_calls == 0


def test_unknown_conversation_is_404(user, ai, post_turn):
    r, _ = post_turn(user["headers"], "00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_ended_sessions_reject_further_turns(client, user, start_session, ai, post_turn):
    cid = start_session(user["headers"])
    client.post(f"/api/conversation/{cid}/end", headers=user["headers"])
    r, _ = post_turn(user["headers"], cid)
    assert r.status_code == 409 and ai.stt_calls == 0


def test_the_old_batch_endpoint_is_gone(client, user, start_session):
    cid = start_session(user["headers"])
    r = client.post("/api/conversation/message", headers=user["headers"], data={"conversation_id": cid}, files={"audio_file": ("a.webm", b"x", "audio/webm")})
    assert r.status_code in (404, 405)


# ── Limits ────────────────────────────────────────────────────────────────────

def test_oversized_uploads_are_cut_off_before_buffering(client, user, start_session, ai, post_turn):
    cid = start_session(user["headers"])
    r, _ = post_turn(user["headers"], cid, audio=b"0" * (6 * 1024 * 1024))
    assert r.status_code == 413 and ai.stt_calls == 0


def test_uploads_just_over_the_cap_are_rejected_by_the_handler(client, user, start_session, ai, post_turn):
    from backend.config import MAX_AUDIO_BYTES

    cid = start_session(user["headers"])
    r, _ = post_turn(user["headers"], cid, audio=b"0" * (MAX_AUDIO_BYTES + 1000))   # under the middleware's slack, over the cap
    assert r.status_code == 413 and ai.stt_calls == 0


def test_uploads_within_the_cap_are_accepted(user, start_session, ai, post_turn):
    r, events = post_turn(user["headers"], start_session(user["headers"]), audio=b"0" * (1024 * 1024))
    assert r.status_code == 200 and _types(events)[-1] == "done"


def test_turn_rate_limit_per_user(user, start_session, ai, post_turn):
    cid = start_session(user["headers"])
    ai.reply_tokens = ["Okay."]
    statuses = [post_turn(user["headers"], cid)[0].status_code for _ in range(32)]
    assert statuses[:30] == [200] * 30 and statuses[30:] == [429, 429]


def test_upload_temp_files_are_cleaned_up(user, start_session, ai, post_turn):
    import tempfile
    from pathlib import Path

    before = set(Path(tempfile.gettempdir()).glob("tmp*.webm"))
    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)
    ai.stt_error = RuntimeError("boom")
    post_turn(user["headers"], cid)
    assert set(Path(tempfile.gettempdir()).glob("tmp*.webm")) - before == set()


# ── Async analysis ────────────────────────────────────────────────────────────

def test_analysis_runs_concurrently_and_exposes_a_pending_count(client, user, start_session, ai, post_turn, wait_for_analysis):
    ai.analysis_gate = threading.Event()
    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)

    during = client.get(f"/api/analysis/conversation/{cid}/recent", headers=user["headers"]).json()
    assert during["pending"] == 1 and during["corrections"] == []     # "still coming", not "none"

    ai.analysis_gate.set()
    assert wait_for_analysis(cid)
    after = client.get(f"/api/analysis/conversation/{cid}/recent", headers=user["headers"]).json()
    assert after["pending"] == 0 and len(after["corrections"]) == 1
    c = after["corrections"][0]
    assert (c["category"], c["subtype"], c["is_error"], c["severity"]) == ("grammar", "past_tense", True, "high")


def test_analysis_starts_before_the_stream_finishes(user, start_session, ai, post_turn, monkeypatch):
    """Regression: it used to start only after `done`, so feedback always arrived a turn late."""
    from backend.services import llm

    seen = {}

    def reply_stream(messages, *a, **k):
        # By the time the LLM is asked for the reply, analysis must already be under way.
        seen["analysis_started"] = _wait_for(lambda: len(ai.analysis_calls) >= 1)
        yield "Okay."

    monkeypatch.setattr(llm, "chat_stream", reply_stream)
    post_turn(user["headers"], start_session(user["headers"]))
    assert seen["analysis_started"] is True


def _wait_for(predicate, timeout=2.0):
    import time

    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_analysis_failure_resolves_the_pending_state(client, user, start_session, ai, post_turn, wait_for_analysis, db):
    ai.analysis_error = RuntimeError("llm down")
    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)
    assert wait_for_analysis(cid)
    assert db.query(Message).filter_by(role="user").one().analysis_status == "failed"
    assert client.get(f"/api/analysis/conversation/{cid}/recent", headers=user["headers"]).json()["pending"] == 0


def test_very_short_turns_skip_analysis(user, start_session, ai, post_turn, db):
    ai.transcript = "Hi"
    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)
    assert db.query(Message).filter_by(role="user").one().analysis_status == "skipped"
    assert ai.analysis_calls == []


def test_malformed_corrections_are_skipped_individually(client, user, start_session, ai, post_turn, wait_for_analysis):
    good = {"category": "grammar", "subtype": "article", "original": "a apple", "correction": "an apple", "explanation": "Use 'an' before vowel sounds."}
    ai.transcript = "I have a apple and a orange in my bag"
    ai.analysis_payload = {"corrections": [{"category": "astrology", "subtype": "x", "original": "a", "correction": "b", "explanation": "c"}, good]}
    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)
    assert wait_for_analysis(cid)
    corrections = client.get(f"/api/analysis/conversation/{cid}/recent", headers=user["headers"]).json()["corrections"]
    assert [c["subtype"] for c in corrections] == ["articles"]      # normalised onto the taxonomy


def test_unparseable_analysis_output_is_a_failure_not_a_crash(client, user, start_session, ai, post_turn, wait_for_analysis, db):
    ai.analysis_payload = "this is not json"
    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)
    assert wait_for_analysis(cid)
    assert db.query(Message).filter_by(role="user").one().analysis_status == "failed"


def test_analysis_prompt_knows_the_learners_english_variety(user, start_session, ai, post_turn, wait_for_analysis):
    cid = start_session(user["headers"], style="british")
    post_turn(user["headers"], cid)
    wait_for_analysis(cid)
    assert "British English" in ai.analysis_calls[0][0]["content"]


def test_analysis_endpoint_is_owner_only_and_validates_limit(client, user, make_user, start_session):
    cid = start_session(user["headers"])
    other = make_user("other@example.com")
    assert client.get(f"/api/analysis/conversation/{cid}/recent", headers=other["headers"]).status_code == 404
    assert client.get(f"/api/analysis/conversation/{cid}/recent?limit=0", headers=user["headers"]).status_code == 422
    assert client.get(f"/api/analysis/conversation/{cid}/recent").status_code == 401


def test_stale_pending_turns_do_not_keep_clients_polling(client, user, start_session, ai, post_turn, wait_for_analysis, db):
    from datetime import datetime, timedelta, timezone

    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)
    wait_for_analysis(cid)
    db.query(Message).filter_by(role="user").update({"analysis_status": "pending", "created_at": datetime.now(timezone.utc) - timedelta(minutes=10)})
    db.commit()
    assert client.get(f"/api/analysis/conversation/{cid}/recent", headers=user["headers"]).json()["pending"] == 0
