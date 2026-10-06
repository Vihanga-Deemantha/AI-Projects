"""
The analysis pipeline's treatment of model output (services/analysis.py) and the
subtype taxonomy (taxonomy.py). Offline: the LLM is faked, because what matters
here is what we do with whatever it says — it is untrusted input.
"""
import pytest
from pydantic import ValidationError

from backend import taxonomy
from backend.models.core import Correction
from backend.schemas.core import CorrectionItem
from backend.services import analysis


def item(**kw):
    base = {"category": "grammar", "subtype": "past_tense", "original": "I go to the mall", "correction": "I went to the mall",
            "explanation": "Use the simple past.", "is_error": True, "is_positive": False, "severity": "high"}
    return {**base, **kw}


TRANSCRIPT = "Yesterday I go to the mall and it was a piece of cake to find parking."


def clean(*raw, transcript=TRANSCRIPT):
    return analysis.clean_items(list(raw), transcript)


# ── The three kinds of item ───────────────────────────────────────────────────

def test_a_mistake_needs_a_correction():
    with pytest.raises(ValidationError):
        CorrectionItem.model_validate(item(correction=""))
    with pytest.raises(ValidationError):
        CorrectionItem.model_validate(item(correction="   "))


def test_praise_is_never_an_error_never_high_severity_and_repeats_the_wording():
    c = CorrectionItem.model_validate(item(category="naturalness", subtype="idiom_used", original="a piece of cake",
                                           correction="", is_error=True, is_positive=True, severity="high"))
    assert c.is_error is False and c.severity == "low" and c.correction == "a piece of cake"


def test_unknown_categories_and_severities_are_rejected():
    for bad in ({"category": "astrology"}, {"severity": "catastrophic"}, {"original": ""}, {"explanation": ""}):
        with pytest.raises(ValidationError):
            CorrectionItem.model_validate(item(**bad))


def test_booleans_the_model_writes_as_strings_are_understood():
    c = CorrectionItem.model_validate(item(is_error="true", is_positive="false"))
    assert c.is_error is True and c.is_positive is False


# ── The hallucination guard ───────────────────────────────────────────────────

def test_a_correction_quoting_words_the_learner_never_said_is_dropped():
    assert clean(item(original="I goes to the park", correction="I go to the park")) == []


def test_the_quote_check_ignores_case_punctuation_and_curly_quotes():
    spoken = "Well, I don’t know... it's a PIECE of cake!"
    assert analysis.quoted_in("a piece of cake", spoken)
    assert analysis.quoted_in("I don't know", spoken)
    assert not analysis.quoted_in("a piece of pie", spoken)
    assert not analysis.quoted_in("", spoken)


def test_a_correction_that_changes_nothing_is_dropped():
    """e.g. the model 'fixing' a comma — punctuation is an artefact of transcription."""
    comma = item(original="a piece of cake", correction="a piece of cake;", category="grammar", subtype="other")
    assert clean(comma) == []
    assert len(clean(item())) == 1                                   # a real change survives


# ── Praise rules ──────────────────────────────────────────────────────────────

def praise(**kw):
    fields = dict(category="naturalness", subtype="idiom_used", original="a piece of cake", correction="a piece of cake",
                  explanation="Means very easy.", is_error=False, is_positive=True, severity="low")
    return item(**{**fields, **kw})


def test_good_praise_survives():
    [c] = clean(praise())
    assert c.is_positive and c.subtype == "idiom_used" and c.category == "naturalness"


def test_praise_must_point_at_an_expression_not_a_word_or_a_sentence():
    assert clean(praise(original="piece")) == []                                            # a single word
    long_quote = "Yesterday I go to the mall and it was a piece of cake"
    assert clean(praise(original=long_quote, correction=long_quote)) == []                  # practically the whole turn


def test_praise_is_moved_into_naturalness_with_a_praise_subtype():
    [c] = clean(item(category="grammar", subtype="past_tense", original="a piece of cake", correction="", is_positive=True, is_error=False))
    assert c.category == "naturalness" and c.subtype == "good_structure"


# ── Normalising and de-duplicating ────────────────────────────────────────────

def test_subtypes_are_mapped_onto_the_taxonomy():
    [c] = clean(item(subtype="Simple Past"))
    assert c.subtype == "past_tense"
    [c] = clean(item(subtype="something the model made up"))
    assert c.subtype == "other"                                       # unbounded labels could never be counted


def test_the_same_issue_twice_is_reported_once():
    assert len(clean(item(), item(explanation="again"))) == 1
    assert len(clean(item(), item(original="it was a piece of cake", correction="it was easy", subtype="tense"))) == 2   # different issues


def test_the_order_is_mistakes_then_suggestions_then_praise():
    tip = item(category="naturalness", subtype="weak_vocabulary", original="find parking", correction="locate parking",
               is_error=False, severity="low")
    result = clean(praise(), tip, item())
    assert [("ERR" if c.is_error else "PRAISE" if c.is_positive else "tip") for c in result] == ["ERR", "tip", "PRAISE"]


def test_limits_are_enforced():
    many = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen"
    words = many.split()
    mistakes = [item(original=f"{words[i]} {words[i + 1]}", correction=f"{words[i + 1]} {words[i]}", subtype="word_order") for i in range(0, 10, 2)]
    tips = [item(category="naturalness", subtype="weak_vocabulary", original=f"{words[i]} {words[i + 1]}", correction="x", is_error=False, severity="low") for i in range(10, 16, 2)]
    result = analysis.clean_items(mistakes + tips, many)
    assert len(result) <= analysis.MAX_ITEMS
    assert sum(1 for c in result if not c.is_error and not c.is_positive) <= analysis.MAX_SUGGESTIONS


def test_one_bad_item_does_not_discard_the_rest():
    result = clean({"category": "nonsense"}, "not even a dict", item())
    assert len(result) == 1


# ── The background task end to end (fake LLM) ─────────────────────────────────

def test_praise_is_stored_and_flagged(client, user, start_session, ai, post_turn, wait_for_analysis, db):
    ai.transcript = "Yesterday I go to the mall and it was a piece of cake to find parking."
    ai.analysis_payload = {"corrections": [item(), praise()]}
    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)
    assert wait_for_analysis(cid)

    rows = {c.is_positive: c for c in db.query(Correction).all()}
    assert rows[False].subtype == "past_tense" and rows[False].is_error is True
    assert rows[True].subtype == "idiom_used" and rows[True].is_error is False

    recent = client.get(f"/api/analysis/conversation/{cid}/recent", headers=user["headers"]).json()["corrections"]
    assert sorted(c["is_positive"] for c in recent) == [False, True]
    assert {c["label"] for c in recent} == {"Past tense", "Idiom"}              # friendly labels come from the taxonomy


def test_praise_is_not_counted_as_a_correction(client, user, start_session, ai, post_turn, wait_for_analysis):
    ai.transcript = "Yesterday I go to the mall and it was a piece of cake to find parking."
    ai.analysis_payload = {"corrections": [item(), praise()]}
    cid = start_session(user["headers"])
    post_turn(user["headers"], cid)
    wait_for_analysis(cid)

    detail = client.get(f"/api/history/sessions/{cid}", headers=user["headers"]).json()
    assert (detail["correction_count"], detail["praise_count"]) == (1, 1)
    listing = client.get("/api/history/sessions", headers=user["headers"]).json()["sessions"][0]
    assert (listing["correction_count"], listing["praise_count"]) == (1, 1)
    user_msg = next(m for m in detail["messages"] if m["role"] == "user")
    assert sorted(c["is_positive"] for c in user_msg["corrections"]) == [False, True]


def test_the_prompt_lists_every_subtype_the_taxonomy_defines():
    prompt = analysis.ANALYSIS_SYSTEM_PROMPT
    for ids in list(taxonomy.MISTAKE_SUBTYPES.values()) + [taxonomy.SUGGESTION_SUBTYPES, taxonomy.PRAISE_SUBTYPES]:
        for subtype in ids:
            assert subtype in prompt
    assert "{mistake_subtypes}" not in prompt and "{{" not in prompt          # no unrendered template


# ── The taxonomy itself ───────────────────────────────────────────────────────

def test_every_subtype_has_a_label_and_a_focus():
    for category, subtypes in taxonomy.SUBTYPES.items():
        for subtype, info in subtypes.items():
            assert info["label"] and info["focus"], (category, subtype)


def test_every_synonym_points_at_a_real_subtype():
    all_ids = {sid for subtypes in taxonomy.SUBTYPES.values() for sid in subtypes}
    for synonym, target in taxonomy._SYNONYMS.items():
        assert target in all_ids, (synonym, target)


@pytest.mark.parametrize("category,raw,expected", [
    ("grammar", "past_tense", "past_tense"),
    ("grammar", "Past Tense", "past_tense"),
    ("grammar", "simple-past", "past_tense"),
    ("grammar", "S-V agreement", "other"),
    ("grammar", "subject_verb", "subject_verb_agreement"),
    ("grammar", "Article", "articles"),
    ("vocabulary", "collocation", "wrong_collocation"),
    ("naturalness", "phrase", "unnatural_phrasing"),
    ("naturalness", "filler words", "filler_words"),
    ("naturalness", "idiom", "idiom_used"),
    ("grammar", "totally new thing", "other"),
    ("grammar", "", "other"),
])
def test_normalise_subtype(category, raw, expected):
    assert taxonomy.normalise_subtype(category, raw) == expected


def test_labels_and_focus():
    assert taxonomy.label_for("grammar", "past_tense") == "Past tense"
    assert taxonomy.label_for("grammar", "something_new") == "Something new"
    assert "already happened" in taxonomy.focus_for("grammar", "past_tense")
    assert taxonomy.focus_for("grammar", "nope") is None
