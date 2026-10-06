"""The in-memory sliding-window limiter, and sentence splitting (pure functions)."""
import pytest

from backend.services.ratelimit import RateLimiter
from backend.services import tts


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def rl(clock):
    return RateLimiter(clock=clock)


def test_allows_up_to_the_limit_then_blocks(rl):
    assert [rl.check_and_record("b", "k", 3, 60) for _ in range(3)] == [0, 0, 0]
    wait = rl.check_and_record("b", "k", 3, 60)
    assert wait > 0 and wait <= 60


def test_window_slides(rl, clock):
    for _ in range(3):
        rl.check_and_record("b", "k", 3, 60)
    clock.advance(61)
    assert rl.check_and_record("b", "k", 3, 60) == 0


def test_retry_after_counts_down_to_when_the_oldest_event_expires(rl, clock):
    rl.check_and_record("b", "k", 2, 100)
    clock.advance(30)
    rl.check_and_record("b", "k", 2, 100)
    assert rl.retry_after("b", "k", 2, 100) == 70
    clock.advance(40)
    assert rl.retry_after("b", "k", 2, 100) == 30


def test_keys_and_buckets_are_independent(rl):
    rl.check_and_record("login", "a", 1, 60)
    assert rl.check_and_record("login", "a", 1, 60) > 0
    assert rl.check_and_record("login", "b", 1, 60) == 0
    assert rl.check_and_record("signup", "a", 1, 60) == 0


def test_failure_counter_pattern(rl):
    for _ in range(5):
        assert rl.retry_after("fail", "k", 5, 900) == 0
        rl.record("fail", "k", 900)
    assert rl.retry_after("fail", "k", 5, 900) > 0
    rl.clear("fail", "k")
    assert rl.retry_after("fail", "k", 5, 900) == 0


def test_retry_after_does_not_consume_budget(rl):
    for _ in range(10):
        assert rl.retry_after("b", "k", 1, 60) == 0


def test_disabled_limiter_never_blocks(monkeypatch, clock):
    monkeypatch.setattr("backend.services.ratelimit.RATE_LIMITS_ENABLED", False)
    rl = RateLimiter(clock=clock)
    assert all(rl.check_and_record("b", "k", 1, 60) == 0 for _ in range(5))


def test_sweeping_idle_keys_bounds_memory(rl, clock, monkeypatch):
    monkeypatch.setattr("backend.services.ratelimit._SWEEP_THRESHOLD", 50)
    for i in range(60):
        rl.check_and_record("b", f"k{i}", 1, 10)
    clock.advance(7200)
    rl.check_and_record("b", "fresh", 1, 10)       # over the threshold -> sweeps every long-idle key
    assert {key for _bucket, key in rl._hits} == {"fresh"}


# ── tts.split_sentences (drives chunked audio) ────────────────────────────────

def test_split_sentences_waits_for_a_complete_long_enough_sentence():
    sentences, rest = tts.split_sentences("I think that is a really great idea for your next trip. Where would")
    assert sentences == ["I think that is a really great idea for your next trip."]
    assert rest == "Where would"


def test_split_sentences_keeps_short_phrases_together():
    sentences, rest = tts.split_sentences("Sounds good, thanks!")
    assert sentences == [] and rest == "Sounds good, thanks!"


def test_split_sentences_uses_a_comma_only_as_a_safety_valve():
    long_run = "word " * 30 + "and then, we keep going without any full stop at all"
    sentences, rest = tts.split_sentences(long_run)
    assert len(sentences) == 1 and sentences[0].endswith(",")
    assert rest.startswith("we keep going")


def test_first_chunk_can_be_short_but_later_chunks_stay_long():
    opener = "Sounds like a busy day! I hope you found"
    assert tts.split_sentences(opener) == ([], opener)                                    # default: waits for 45 chars
    sentences, rest = tts.split_sentences(opener, min_chars=tts.FIRST_CHUNK_MIN_CHARS)    # first chunk: speaks the opener now
    assert sentences == ["Sounds like a busy day!"] and rest == "I hope you found"
