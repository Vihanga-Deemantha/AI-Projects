"""Session scoring (services/scoring.py): pure maths, so every rule is checked directly."""
import pytest

from backend.services import scoring
from backend.services.scoring import Evidence

LABELS = {("grammar", "past_tense"): "Past tense", ("grammar", "articles"): "Articles (a, an, the)",
          ("vocabulary", "wrong_collocation"): "Word partnerships", ("naturalness", "idiom_used"): "Idiom",
          ("naturalness", "phrasal_verb_used"): "Phrasal verb"}


def mistake(category="grammar", subtype="past_tense", severity="medium", original="I go", correction="I went"):
    return {"category": category, "subtype": subtype, "severity": severity, "original": original, "correction": correction}


def praise(subtype="idiom_used", original="a piece of cake"):
    return {"category": "naturalness", "subtype": subtype, "severity": "low", "original": original, "correction": original}


def tip(subtype="weak_vocabulary"):
    return {"category": "naturalness", "subtype": subtype, "severity": "low", "original": "very good", "correction": "excellent"}


def evidence(**kw):
    base = dict(words_analysed=100, analysed_turns=3, mistakes=[], suggestions=[], praise=[], total_words=100)
    return Evidence(**{**base, **kw})


# ── Dimension scores ──────────────────────────────────────────────────────────

def test_a_flawless_session_scores_full_marks_and_praise_lifts_naturalness_to_the_top():
    s = scoring.compute_scores(evidence(praise=[praise(), praise("phrasal_verb_used", "figure out")], fluency_scores=[95], clarity_scores=[95]))
    assert (s["grammar"], s["vocabulary"], s["naturalness"]) == (100, 100, 100)     # 90 base + 2x5 praise
    assert s["overall"] == 98                                                       # (30*100+25*95+15*100+15*95+15*100)/100 = 98.0


def test_grammar_is_a_density_of_weighted_mistakes_per_100_words():
    assert scoring.compute_scores(evidence(mistakes=[mistake()]))["grammar"] == 96                   # 1.0 weighted / 100 words
    assert scoring.compute_scores(evidence(words_analysed=50, mistakes=[mistake(severity="high")] * 3))["grammar"] == 64   # 4.5 / 50 = 9 per 100


def test_severity_changes_the_weight():
    low, med, high = (scoring.compute_scores(evidence(mistakes=[mistake(severity=s)] * 4))["grammar"] for s in ("low", "medium", "high"))
    assert low > med > high
    assert (low, med, high) == (92, 84, 76)


def test_a_short_answer_cannot_swing_the_score_wildly():
    """One mistake in a 5-word answer is not '20 mistakes per 100 words'."""
    s = scoring.compute_scores(evidence(words_analysed=5, analysed_turns=1, mistakes=[mistake()]))
    assert s["grammar"] == 73                                  # density over max(5, MIN_WORDS=15) words


def test_more_words_means_the_same_mistakes_cost_less():
    few = scoring.compute_scores(evidence(words_analysed=40, mistakes=[mistake()] * 2))["grammar"]
    many = scoring.compute_scores(evidence(words_analysed=200, mistakes=[mistake()] * 2))["grammar"]
    assert many > few


def test_vocabulary_and_grammar_are_scored_separately():
    s = scoring.compute_scores(evidence(mistakes=[mistake("vocabulary", "wrong_collocation"), mistake("vocabulary", "wrong_collocation")]))
    assert s["grammar"] == 100 and s["vocabulary"] == 90      # 2 / 100 words * slope 5


def test_suggestions_lower_naturalness_and_praise_raises_it_with_a_cap():
    base = scoring.compute_scores(evidence())["naturalness"]
    assert base == 90
    assert scoring.compute_scores(evidence(suggestions=[tip(), tip()]))["naturalness"] == 84       # -3 per suggestion/100 words
    assert scoring.compute_scores(evidence(praise=[praise()] * 2))["naturalness"] == 100
    assert scoring.compute_scores(evidence(suggestions=[tip()] * 4, praise=[praise()] * 10))["naturalness"] == 98    # praise is capped at +20


def test_scores_are_clamped_to_0_100():
    s = scoring.compute_scores(evidence(words_analysed=20, mistakes=[mistake(severity="high")] * 30))
    assert s["grammar"] == 0
    assert all(0 <= v <= 100 for v in s.values() if v is not None)


# ── Missing evidence is None, never a flattering 100 ──────────────────────────

def test_if_no_turn_was_analysed_the_analysis_dimensions_are_unknown():
    s = scoring.compute_scores(evidence(analysed_turns=0, words_analysed=0, fluency_scores=[80], clarity_scores=[90]))
    assert (s["grammar"], s["vocabulary"], s["naturalness"]) == (None, None, None)       # "0 mistakes" would be a lie
    assert s["overall"] == round((0.25 * 80 + 0.15 * 90) / 0.40)


def test_without_speech_metrics_only_the_three_analysis_dimensions_count():
    s = scoring.compute_scores(evidence(mistakes=[mistake()]))
    assert s["fluency"] is None and s["clarity"] is None
    assert s["overall"] == round((0.30 * 96 + 0.15 * 100 + 0.15 * 90) / 0.60)


def test_no_evidence_at_all_gives_no_overall():
    s = scoring.compute_scores(evidence(analysed_turns=0, words_analysed=0))
    assert s["overall"] is None


def test_weights_sum_to_one():
    assert sum(scoring.WEIGHTS.values()) == pytest.approx(1.0)


def test_scoring_is_versioned():
    assert isinstance(scoring.SCORING_VERSION, int) and scoring.SCORING_VERSION >= 1


# ── Top errors ────────────────────────────────────────────────────────────────

def test_top_errors_group_rank_and_give_an_example():
    ms = [mistake(original="I go", correction="I went"), mistake(original="I buy", correction="I bought"),
          mistake("grammar", "articles", original="a apple", correction="an apple"),
          mistake("vocabulary", "wrong_collocation", "high", "do a mistake", "make a mistake")]
    top = scoring.top_errors(ms, LABELS)
    assert [(t["subtype"], t["count"]) for t in top] == [("past_tense", 2), ("wrong_collocation", 1), ("articles", 1)]
    assert top[0]["label"] == "Past tense" and top[0]["example_original"] == "I go" and top[0]["example_correction"] == "I went"


def test_top_errors_are_limited_and_unknown_labels_fall_back():
    ms = [mistake("grammar", f"made_up_{i}") for i in range(8)]
    top = scoring.top_errors(ms, LABELS, limit=5)
    assert len(top) == 5 and top[0]["label"] == "Made up 0"


# ── What the learner reads ────────────────────────────────────────────────────

def test_strengths_lead_with_specific_praise():
    e = evidence(praise=[praise(), praise(original="break the ice"), praise("phrasal_verb_used", "figure out")], fluency_scores=[90], clarity_scores=[90])
    s = scoring.build_strengths(e, scoring.compute_scores(e), LABELS)
    assert s[0].startswith("Good use of idiom") and "“a piece of cake”" in s[0] and "“break the ice”" in s[0]
    assert any("phrasal verb" in x for x in s) and len(s) <= 3


def test_a_clean_multi_turn_session_says_so():
    e = evidence(analysed_turns=3)
    assert "No grammar or vocabulary mistakes this session" in scoring.build_strengths(e, scoring.compute_scores(e), LABELS)
    e = evidence(analysed_turns=1)
    assert "No grammar or vocabulary mistakes this session" not in scoring.build_strengths(e, scoring.compute_scores(e), LABELS)


def test_a_comfortable_pace_is_a_strength_but_an_extreme_one_is_not():
    for wpm, expected in ((130, True), (60, False), (200, False)):
        e = evidence(wpm_values=[float(wpm)], mistakes=[mistake()])
        assert any("speaking pace" in x for x in scoring.build_strengths(e, scoring.compute_scores(e), LABELS)) is expected


def test_strong_dimensions_become_strengths():
    e = evidence(mistakes=[mistake()], fluency_scores=[92], clarity_scores=[50])
    s = scoring.build_strengths(e, scoring.compute_scores(e), LABELS)
    assert "Fluent, steady delivery" in s and not any("recognise" in x for x in s)


def test_improvements_name_the_top_mistakes_with_examples():
    e = evidence(mistakes=[mistake(), mistake(), mistake("grammar", "articles", original="a apple", correction="an apple")])
    errors = scoring.top_errors(e.mistakes, LABELS)
    imp = scoring.build_improvements(e, scoring.compute_scores(e), errors)
    assert imp[0] == "Past tense — 2 mistakes (e.g. “I go” → “I went”)"
    assert imp[1] == "Articles (a, an, the) — 1 mistake (e.g. “a apple” → “an apple”)"


def test_filler_words_are_flagged_by_rate_not_by_count():
    chatty = evidence(total_words=100, filler_total=8, filler_breakdown={"um": 5, "like": 3})
    assert any("filler words (um ×5, like ×3)" in x for x in scoring.build_improvements(chatty, scoring.compute_scores(chatty), []))
    long_and_fluent = evidence(total_words=1000, filler_total=8, filler_breakdown={"um": 8})
    assert not any("filler" in x for x in scoring.build_improvements(long_and_fluent, scoring.compute_scores(long_and_fluent), []))


def test_pace_pauses_and_unclear_words_are_surfaced():
    slow = evidence(wpm_values=[70.0])
    assert any("Speak a little faster" in x for x in scoring.build_improvements(slow, scoring.compute_scores(slow), []))
    fast = evidence(wpm_values=[200.0])
    assert any("Slow down" in x for x in scoring.build_improvements(fast, scoring.compute_scores(fast), []))
    pausey = evidence(long_pause_total=3)
    assert any("long pauses" in x for x in scoring.build_improvements(pausey, scoring.compute_scores(pausey), []))
    unclear = evidence(unclear_words={"comfortable": 3, "particularly": 1, "library": 1})
    assert any(x == "Practise saying: comfortable, library, particularly" for x in scoring.build_improvements(unclear, scoring.compute_scores(unclear), []))


def test_repeated_basic_vocabulary_suggestions_become_advice():
    e = evidence(suggestions=[tip(), tip()])
    assert any("stronger, more varied words" in x for x in scoring.build_improvements(e, scoring.compute_scores(e), []))
    e = evidence(suggestions=[tip("unnatural_phrasing"), tip("unnatural_phrasing")])
    assert not any("stronger" in x for x in scoring.build_improvements(e, scoring.compute_scores(e), []))


def test_improvements_are_limited_to_three():
    e = evidence(mistakes=[mistake()] * 3 + [mistake("grammar", "articles")] * 2, total_words=50, filler_total=9, filler_breakdown={"um": 9},
                 wpm_values=[60.0], unclear_words={"hard": 2})
    assert len(scoring.build_improvements(e, scoring.compute_scores(e), scoring.top_errors(e.mistakes, LABELS))) == 3


def test_a_clean_session_has_nothing_to_improve():
    e = evidence(fluency_scores=[95], wpm_values=[130.0])
    assert scoring.build_improvements(e, scoring.compute_scores(e), []) == []
