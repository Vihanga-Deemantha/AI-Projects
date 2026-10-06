"""The helper that makes the live regression suite tolerant of run-to-run variation, tested offline."""
import pytest

from backend.services.analysis import CorrectionItem
from backend.tests.regression import test_analysis_quality as live


def item(**kw):
    base = dict(category="naturalness", subtype="phrasal_verb_used", original="figure out", correction="figure out",
                explanation="x", is_error=False, is_positive=True, severity="low")
    return CorrectionItem(**{**base, **kw})


PRAISED = [item()]
NOTHING: list = []
TIP = [item(subtype="advanced_alternative", is_positive=False)]
MISTAKE = [item(category="grammar", subtype="other", is_error=True, is_positive=False)]


def scripted(monkeypatch, *outcomes):
    calls = []

    def fake_run(transcript, style="standard"):
        calls.append(transcript)
        return outcomes[len(calls) - 1]

    monkeypatch.setattr(live, "run", fake_run)
    return calls


def test_it_accepts_the_first_attempt_that_shows_the_behaviour_and_stops_there(monkeypatch):
    calls = scripted(monkeypatch, NOTHING, PRAISED, MISTAKE)
    assert live.best_of("x", 3, lambda items: bool(live.praise(items))) == PRAISED
    assert len(calls) == 2                                           # never ran the third, which would have failed


def test_it_fails_when_the_behaviour_never_happens(monkeypatch):
    scripted(monkeypatch, NOTHING, TIP, NOTHING)
    with pytest.raises(AssertionError, match="did not happen in 3 attempts"):
        live.best_of("x", 3, lambda items: bool(live.praise(items)))


def test_a_mistake_in_any_attempt_fails_even_if_a_later_one_would_pass(monkeypatch):
    scripted(monkeypatch, MISTAKE, PRAISED)
    with pytest.raises(AssertionError, match="flagged correct English"):
        live.best_of("x", 3, lambda items: bool(live.praise(items)))


def test_a_mistake_alongside_praise_still_fails(monkeypatch):
    scripted(monkeypatch, PRAISED + MISTAKE)
    with pytest.raises(AssertionError, match="flagged correct English"):
        live.best_of("x", 3, lambda items: bool(live.praise(items)))
