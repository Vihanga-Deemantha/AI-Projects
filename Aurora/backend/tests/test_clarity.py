"""Clarity (speech-recognition confidence): the maths, the API, and the 'hear this word' endpoint."""
import json
import math

import pytest

from backend.models.metrics import ClarityScore
from backend.services import clarity, stt, tts


def words(*pairs):
    """words(("hello", 0.97), ("comfortable", 0.42)) -> recogniser-style word dicts"""
    out, t = [], 0.0
    for text, prob in pairs:
        out.append({"word": text, "start": round(t, 2), "end": round(t + 0.4, 2), "probability": prob})
        t += 0.5
    return out


# ── The maths ─────────────────────────────────────────────────────────────────

def test_clean_speech_scores_high_and_has_nothing_to_flag():
    m = clarity.analyse(words(*[(f"word{i}", 0.97) for i in range(12)]), avg_logprob=-0.2)
    assert m.word_level is True and m.score >= 95
    assert m.unclear_words == [] and m.words_scored == 12 and m.avg_word_confidence == pytest.approx(0.97)


def test_unclear_words_are_listed_least_clear_first():
    m = clarity.analyse(words(("I", 0.99), ("would", 0.95), ("particularly", 0.61), ("recommend", 0.93), ("comfortable", 0.43)), -0.3)
    assert [w["word"] for w in m.unclear_words] == ["comfortable", "particularly"]
    assert m.unclear_words[0]["probability"] == 0.43


def test_short_function_words_are_never_flagged():
    m = clarity.analyse(words(("a", 0.2), ("to", 0.3), ("the", 0.4), ("it", 0.1), ("with", 0.3), ("That", 0.2), ("restaurant", 0.95)), -0.3)
    assert m.unclear_words == []                     # nothing worth practising among the low-confidence "words"
    assert m.score < 75                              # ...though they do still count toward the score
    assert [w["word"] for w in clarity.analyse(words(("tea", 0.3), ("the", 0.3)), -0.3).unclear_words] == ["tea"]   # short content words are kept


def test_the_list_is_capped_and_punctuation_is_stripped():
    ws = words(*[(f"Word{chr(97 + i)}{chr(97 + i)}.", 0.1 + i * 0.05) for i in range(8)])
    m = clarity.analyse(ws, -0.5)
    assert len(m.unclear_words) == clarity.MAX_UNCLEAR_WORDS
    assert m.unclear_words[0]["word"] == "Wordaa"
    assert [w["probability"] for w in m.unclear_words] == sorted(w["probability"] for w in m.unclear_words)


def test_the_threshold_boundary():
    m = clarity.analyse(words(("exactly", 0.80), ("barely", 0.79), ("fine", 0.81)), -0.2)
    assert [w["word"] for w in m.unclear_words] == ["barely"]


def test_hesitation_sounds_are_not_scored():
    m = clarity.analyse(words(("um", 0.1), ("hello", 0.97), ("uh", 0.1), ("there", 0.97)), -0.2)
    assert m.words_scored == 2 and m.unclear_words == []


def test_the_score_blends_mean_confidence_with_the_share_of_confident_words():
    # 18 clear words + 2 unclear: mean 0.913, 90% confident -> 0.6*0.913 + 0.4*0.9 = 0.908
    assert clarity.score_from_word_confidences([0.97] * 18 + [0.4] * 2) == 91
    assert clarity.score_from_word_confidences([0.98] * 10) == 99     # 0.6*0.98 + 0.4*1.0
    assert clarity.score_from_word_confidences([0.3] * 10) == 18
    assert clarity.score_from_word_confidences([]) == 0


def test_calibration_matches_what_was_measured_on_real_whisper_output():
    clean = [0.98, 0.97, 0.96, 0.97, 0.95, 0.99, 0.97, 0.98]                     # synthetic clean speech: mean ~0.97
    muffled = [0.95, 0.9, 0.82, 0.08, 0.24, 0.74, 0.97, 0.88, 0.9, 0.93]         # low-passed audio: mean ~0.74-0.82
    assert clarity.score_from_word_confidences(clean) >= 95
    assert 60 <= clarity.score_from_word_confidences(muffled) <= 85
    assert clarity.score_from_word_confidences(clean) > clarity.score_from_word_confidences(muffled) + 12


def test_no_words_means_no_clarity():
    assert clarity.analyse([], -0.2) is None
    assert clarity.analyse(words(("um", 0.9), ("uh", 0.9)), -0.2) is None


# ── Without per-word confidence (hosted recogniser) ───────────────────────────

def test_segment_level_fallback_is_flagged_and_gives_no_word_list():
    m = clarity.analyse(words(("hello", None), ("there", None), ("friend", None)), avg_logprob=-0.25)
    assert m.word_level is False and m.avg_word_confidence is None and m.unclear_words == []
    assert m.score == round(100 * (math.exp(-0.25) - 0.4) / 0.45)


@pytest.mark.parametrize("logprob,expected", [(0.0, 100), (-0.1, 100), (-0.25, 84), (-0.45, 54), (-1.0, 0), (-3.0, 0)])
def test_the_segment_level_mapping(logprob, expected):
    assert clarity.score_from_logprob(logprob) == pytest.approx(expected, abs=1)


def test_perfect_audio_does_not_read_as_78_percent():
    """exp(avg_logprob) is ~0.78 even for pristine audio; shown raw it would look mediocre."""
    assert clarity.score_from_logprob(math.log(0.78)) >= 80


def test_output_is_plain_json():
    m = clarity.analyse(words(("comfortable", 0.43), ("restaurant", 0.9)), -0.3)
    json.dumps(m.to_dict())


# ── Through the API ───────────────────────────────────────────────────────────

def test_a_turn_stores_clarity_and_sends_it_with_the_metrics(user, start_session, ai, post_turn, db):
    ai.words = words(("I", 0.99), ("particularly", 0.55), ("recommend", 0.95), ("comfortable", 0.4), ("seats", 0.93))
    ai.transcript = "I particularly recommend comfortable seats"
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    c = events[1]["clarity"]
    assert c["word_level"] is True and [w["word"] for w in c["unclear_words"]] == ["comfortable", "particularly"]

    row = db.query(ClarityScore).one()
    assert row.message_id == events[0]["message_id"] and row.score == c["score"]
    assert [w["word"] for w in row.unclear_words] == ["comfortable", "particularly"]


def test_the_hosted_recogniser_path_reports_a_rough_estimate(user, start_session, ai, post_turn):
    ai.words = [{**w, "probability": None} for w in ai.build_words()]
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert events[1]["clarity"]["word_level"] is False and events[1]["clarity"]["unclear_words"] == []


def test_a_clarity_bug_does_not_lose_the_fluency_metrics(user, start_session, ai, post_turn, monkeypatch, db):
    from backend.models.metrics import FluencyScore

    monkeypatch.setattr(clarity, "analyse", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bug")))
    _, events = post_turn(user["headers"], start_session(user["headers"]))
    assert events[1]["clarity"] is None and events[1]["fluency"] is not None
    assert db.query(FluencyScore).count() == 1 and db.query(ClarityScore).count() == 0


def test_history_includes_clarity_per_turn_and_averages(client, user, start_session, ai, post_turn, wait_for_analysis):
    cid = start_session(user["headers"])
    for text, prob in (("first turn spoken clearly", 0.97), ("second turn was much harder to catch", 0.5)):
        ai.transcript = text
        ai.words = [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4, "probability": prob} for i, w in enumerate(text.split())]
        post_turn(user["headers"], cid)
    wait_for_analysis(cid)

    d = client.get(f"/api/history/sessions/{cid}", headers=user["headers"]).json()
    scores = [m["clarity"]["score"] for m in d["messages"] if m["role"] == "user"]
    assert scores[0] > scores[1] and d["avg_clarity"] == round(sum(scores) / 2)
    assert d["messages"][1]["clarity"] is None                       # assistant turns have none
    assert client.get("/api/history/sessions", headers=user["headers"]).json()["sessions"][0]["avg_clarity"] == d["avg_clarity"]


def test_account_deletion_removes_clarity_rows(client, user, start_session, ai, post_turn, db):
    from backend.tests.conftest import PASSWORD

    post_turn(user["headers"], start_session(user["headers"]))
    assert db.query(ClarityScore).count() == 1
    client.request("DELETE", "/api/auth/account", headers=user["headers"], json={"confirm_email": user["email"], "password": PASSWORD})
    db.expire_all()
    assert db.query(ClarityScore).count() == 0


# ── "Hear this word" ──────────────────────────────────────────────────────────

def test_word_audio_requires_auth(client):
    assert client.post("/api/speech/word", json={"word": "comfortable"}).status_code == 401


def test_word_audio_returns_wav_in_the_users_preferred_voice(client, user, ai):
    client.patch("/api/auth/profile", headers=user["headers"], json={"preferred_voice": "alan"})
    r = client.post("/api/speech/word", headers=user["headers"], json={"word": "Comfortable"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert r.content.startswith(b"RIFF") and "max-age" in r.headers["cache-control"]
    assert ai.tts_calls == [("comfortable", "alan", None)]            # lower-cased, normal speed


def test_word_audio_can_be_slow_and_can_name_a_voice(client, user, ai):
    r = client.post("/api/speech/word", headers=user["headers"], json={"word": "particularly", "voice": "ryan", "slow": True})
    assert r.status_code == 200
    assert ai.tts_calls == [("particularly", "ryan", tts.SLOW_LENGTH_SCALE)]


def test_word_audio_is_cached(client, user, ai):
    for _ in range(3):
        client.post("/api/speech/word", headers=user["headers"], json={"word": "library"})
    assert len(ai.tts_calls) == 1
    client.post("/api/speech/word", headers=user["headers"], json={"word": "library", "slow": True})
    assert len(ai.tts_calls) == 2                                      # slow is a different clip


@pytest.mark.parametrize("word", ["", "two words", "123", "semi;colon", "x" * 41, "-dash", "ünïcode", "<b>"])
def test_word_audio_only_accepts_a_single_word(client, user, ai, word):
    assert client.post("/api/speech/word", headers=user["headers"], json={"word": word}).status_code == 422
    assert ai.tts_calls == []


def test_word_audio_accepts_apostrophes_and_hyphens(client, user, ai):
    for word in ("don't", "well-known", "O'Brien"):
        assert client.post("/api/speech/word", headers=user["headers"], json={"word": word}).status_code == 200


def test_word_audio_rejects_unknown_and_uninstalled_voices(client, user, ai, monkeypatch):
    assert client.post("/api/speech/word", headers=user["headers"], json={"word": "hello", "voice": "nope"}).status_code == 400
    monkeypatch.setattr(tts, "voice_available", lambda v: v != "ryan")
    assert client.post("/api/speech/word", headers=user["headers"], json={"word": "hello", "voice": "ryan"}).status_code == 400


def test_word_audio_failures_are_generic(client, user, ai):
    ai.tts_error = RuntimeError("onnx exploded at C:\\secret")
    r = client.post("/api/speech/word", headers=user["headers"], json={"word": "hello"})
    assert r.status_code == 503 and "onnx" not in r.text and "secret" not in r.text


def test_word_audio_is_rate_limited(client, user, ai):
    codes = [client.post("/api/speech/word", headers=user["headers"], json={"word": "hello"}).status_code for _ in range(62)]
    assert codes[:60] == [200] * 60 and codes[60:] == [429, 429]
