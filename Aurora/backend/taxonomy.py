"""
The vocabulary of feedback: every kind of correction AURA can give.

One table, used everywhere a subtype matters:

  * the analysis prompt lists these ids, so the model uses a fixed vocabulary;
  * normalise_subtype() maps whatever the model actually returns onto it, which is
    what makes "you keep getting past tense wrong" countable across sessions
    (Phase 9 weakness profiling groups by subtype — if one session says
    "past_tense" and the next "simple_past" the habit would never show up);
  * the UI turns ids into labels, and the daily exercise picks its `focus` text.

Adding a subtype is a one-line change here.
"""
import re

# category -> subtype id -> {label, focus}
#   label: what a learner sees ("Past tense").
#   focus: a steering instruction for the coach, used to practise a weakness
#          (Phase 9) — it says what to make the conversation about, never to quiz.
SUBTYPES: dict[str, dict[str, dict[str, str]]] = {
    "grammar": {
        "past_tense": {"label": "Past tense", "focus": "things that already happened — yesterday, last weekend, a past trip — so the user must use the simple past"},
        "present_perfect": {"label": "Present perfect", "focus": "life experiences and recent news (have you ever…, what have you done this week) so the user must use the present perfect"},
        "tense": {"label": "Verb tense", "focus": "plans, habits and past events in turn, so the user has to switch tenses naturally"},
        "subject_verb_agreement": {"label": "Subject–verb agreement", "focus": "what other people do (he, she, my friend, my family) so the user must match verbs to subjects"},
        "articles": {"label": "Articles (a, an, the)", "focus": "describing specific things and places the user knows (the café near work, a favourite book) so the user must choose a, an or the"},
        "prepositions": {"label": "Prepositions", "focus": "times, places and directions (at six, in March, on the left) so the user must pick the right preposition"},
        "plurals": {"label": "Plurals", "focus": "counting and listing things (how many friends, what you bought) so the user must form plurals"},
        "word_order": {"label": "Word order", "focus": "longer descriptive answers and questions, so the user has to build full sentences"},
        "pronouns": {"label": "Pronouns", "focus": "talking about different people in the same story, so the user must choose he, she, they, him, her"},
        "modal_verbs": {"label": "Modal verbs", "focus": "advice, ability and obligation (what should I do, what can you do, what must you do) so the user must use can, should, must"},
        "conditionals": {"label": "Conditionals (if…)", "focus": "hypothetical situations (what would you do if…) so the user must use conditionals"},
        "comparatives": {"label": "Comparatives", "focus": "comparing things and places (which is better, bigger, more interesting) so the user must use comparatives"},
        "gerund_infinitive": {"label": "Gerunds & infinitives", "focus": "likes, plans and decisions (I enjoy…, I want to…, I'm thinking of…) so the user must choose -ing or to"},
        "countable_uncountable": {"label": "Countable / uncountable nouns", "focus": "food, advice and information (how much, how many) so the user must choose much/many and a/some"},
        "question_formation": {"label": "Forming questions", "focus": "inviting the user to ask YOU questions about your day or your job, so they must build questions"},
        "negation": {"label": "Negatives", "focus": "things the user doesn't do or didn't like, so the user must form negatives"},
        "other": {"label": "Grammar", "focus": "everyday topics that need full, accurate sentences"},
    },
    "vocabulary": {
        "wrong_word": {"label": "Wrong word", "focus": "specific, concrete topics where the exact word matters (a recipe, a hobby, a job)"},
        "wrong_collocation": {"label": "Word partnerships", "focus": "everyday actions (make a decision, do homework, take a break, have a shower) so the user needs natural verb+noun pairs"},
        "word_form": {"label": "Word form", "focus": "opinions and descriptions (an interesting idea, interested in, interest) so the user must use the right word form"},
        "false_friend": {"label": "False friend", "focus": "everyday life topics where look-alike words from other languages cause slips"},
        "register": {"label": "Formal vs casual", "focus": "switching between a casual chat and a formal request, so the user must adjust their register"},
        "other": {"label": "Vocabulary", "focus": "varied topics that need precise vocabulary"},
    },
    "naturalness": {
        "unnatural_phrasing": {"label": "More natural phrasing", "focus": "opinions and stories told in the user's own words"},
        "weak_vocabulary": {"label": "Stronger vocabulary", "focus": "describing experiences, feelings and places in detail so the user reaches for richer words than good, bad, nice"},
        "overused_expression": {"label": "Overused words", "focus": "describing several different things in a row, so the user must vary their wording"},
        "advanced_alternative": {"label": "A more advanced way to say it", "focus": "topics that invite fuller, more expressive answers"},
        "filler_words": {"label": "Filler words", "focus": "explaining something step by step, so the user has to organise their thoughts instead of filling gaps"},
        # Praise — what the learner did well.
        "idiom_used": {"label": "Idiom", "focus": "casual stories where idioms come up naturally"},
        "phrasal_verb_used": {"label": "Phrasal verb", "focus": "daily routines and problem-solving, where phrasal verbs are everywhere"},
        "good_collocation": {"label": "Natural word pairing", "focus": "everyday topics"},
        "good_structure": {"label": "Well-built sentence", "focus": "longer, more detailed answers"},
        "other": {"label": "Naturalness", "focus": "everyday topics told naturally"},
    },
}

CATEGORIES = tuple(SUBTYPES)

# What models tend to write instead of our ids.
_SYNONYMS = {
    "verb_tense": "tense", "tenses": "tense", "wrong_tense": "tense", "tense_error": "tense",
    "past_simple": "past_tense", "simple_past": "past_tense", "past": "past_tense", "past_tense_error": "past_tense",
    "perfect": "present_perfect", "present_perfect_tense": "present_perfect",
    "subject_verb": "subject_verb_agreement", "sv_agreement": "subject_verb_agreement", "agreement": "subject_verb_agreement",
    "subject_verb_agreement_error": "subject_verb_agreement", "verb_agreement": "subject_verb_agreement",
    "article": "articles", "missing_article": "articles", "article_usage": "articles",
    "preposition": "prepositions", "preposition_usage": "prepositions", "wrong_preposition": "prepositions",
    "plural": "plurals", "plural_form": "plurals", "noun_plural": "plurals",
    "modal": "modal_verbs", "modals": "modal_verbs", "modal_verb": "modal_verbs",
    "conditional": "conditionals", "if_clause": "conditionals",
    "comparative": "comparatives", "comparison": "comparatives",
    "gerund": "gerund_infinitive", "infinitive": "gerund_infinitive", "gerunds": "gerund_infinitive",
    "countable": "countable_uncountable", "uncountable": "countable_uncountable",
    "questions": "question_formation", "question": "question_formation",
    "negative": "negation", "negatives": "negation",
    "pronoun": "pronouns", "pronoun_usage": "pronouns",
    "collocation": "wrong_collocation", "collocations": "wrong_collocation", "wrong_collocations": "wrong_collocation",
    "word_choice": "wrong_word", "incorrect_word": "wrong_word", "wrong_word_choice": "wrong_word", "word_usage": "wrong_word",
    "formality": "register", "tone": "register",
    "phrase": "unnatural_phrasing", "phrasing": "unnatural_phrasing", "awkward_phrasing": "unnatural_phrasing",
    "unnatural": "unnatural_phrasing", "naturalness": "unnatural_phrasing", "natural_phrasing": "unnatural_phrasing",
    "basic_vocabulary": "weak_vocabulary", "vocabulary_upgrade": "weak_vocabulary", "repetition": "overused_expression",
    "overused": "overused_expression", "overused_word": "overused_expression", "repetitive": "overused_expression",
    "filler": "filler_words", "fillers": "filler_words", "filler_word": "filler_words",
    "idiom": "idiom_used", "idioms": "idiom_used", "good_idiom": "idiom_used",
    "phrasal_verb": "phrasal_verb_used", "phrasal_verbs": "phrasal_verb_used", "phrasal": "phrasal_verb_used",
    "collocation_used": "good_collocation", "natural_collocation": "good_collocation",
    "structure": "good_structure", "complex_sentence": "good_structure",
}


def _slug(raw: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(raw).lower())).strip("_")


def normalise_subtype(category: str, raw: str) -> str:
    """
    Maps a model-written subtype onto the canonical id for `category`. An id that
    is already canonical is kept; a known synonym is mapped; anything else becomes
    the category's catch-all ("other") rather than an unbounded new label that
    could never be counted.
    """
    options = SUBTYPES.get(category, {})
    slug = _slug(raw)
    if slug in options:
        return slug
    mapped = _SYNONYMS.get(slug)
    if mapped in options:
        return mapped
    return "other"


def label_for(category: str, subtype: str) -> str:
    return SUBTYPES.get(category, {}).get(subtype, {}).get("label") or subtype.replace("_", " ").capitalize()


def focus_for(category: str, subtype: str) -> str | None:
    return SUBTYPES.get(category, {}).get(subtype, {}).get("focus")


# The three kinds of feedback and which subtypes belong to each. A correction is
# a MISTAKE (is_error), a SUGGESTION (right, but could be better) or PRAISE
# (is_positive: notably good use of English). The prompt shows each kind its own list.
PRAISE_SUBTYPES = ("idiom_used", "phrasal_verb_used", "good_collocation", "good_structure")
SUGGESTION_SUBTYPES = ("unnatural_phrasing", "weak_vocabulary", "overused_expression", "advanced_alternative", "filler_words")
MISTAKE_SUBTYPES = {
    "grammar": tuple(SUBTYPES["grammar"]),
    "vocabulary": tuple(SUBTYPES["vocabulary"]),
}


def is_praise_subtype(subtype: str) -> bool:
    return subtype in PRAISE_SUBTYPES


# The scenario in which a weakness comes up most naturally — used to suggest one
# for today's practice. Anything not listed falls back to casual conversation.
PRACTICE_SCENARIO = {
    "past_tense": "casual", "present_perfect": "interview", "tense": "casual",
    "subject_verb_agreement": "casual", "articles": "cafe", "prepositions": "travel",
    "plurals": "cafe", "word_order": "debate", "pronouns": "casual", "modal_verbs": "travel",
    "conditionals": "debate", "comparatives": "debate", "gerund_infinitive": "interview",
    "countable_uncountable": "cafe", "question_formation": "phone", "negation": "casual",
    "wrong_collocation": "casual", "wrong_word": "seminar", "word_form": "seminar", "register": "interview",
    "unnatural_phrasing": "casual", "weak_vocabulary": "seminar", "overused_expression": "debate",
    "filler_words": "seminar",
}


def scenario_for(subtype: str) -> str:
    return PRACTICE_SCENARIO.get(subtype, "casual")


def focus_id(category: str, subtype: str) -> str:
    return f"{category}:{subtype}"


def parse_focus(value: str | None) -> tuple[str, str] | None:
    """'grammar:past_tense' -> ('grammar', 'past_tense'); None if it isn't a real subtype (never trust a client's focus)."""
    if not value or ":" not in value:
        return None
    category, _, subtype = value.partition(":")
    return (category, subtype) if subtype in SUBTYPES.get(category, {}) else None
