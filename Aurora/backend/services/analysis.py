"""
Grammar / vocabulary / naturalness analysis of one spoken turn (the "async path").

Runs in the background while the coach is still speaking (services/background.py)
and writes `corrections` rows. Three kinds of feedback come back from one LLM
call — mistakes, suggestions and praise — and everything the model returns is
treated as untrusted input:

  * each item is validated individually, so one malformed entry can't discard the batch;
  * subtypes are normalised onto the fixed taxonomy (taxonomy.py) so they can be
    counted across sessions;
  * an item whose quoted `original` isn't actually in the transcript is dropped —
    a model that "corrects" words the learner never said is worse than no model;
  * counts are capped and ordered (mistakes first), duplicates removed.
"""
import json
import logging
import re

from pydantic import ValidationError

from backend import taxonomy
from backend.database import SessionLocal
from backend.models.core import Correction, Message
from backend.personalities import DEFAULT_STYLE, STYLES
from backend.schemas.core import CorrectionItem
from backend.services import llm

logger = logging.getLogger("aura.analysis")

MAX_ITEMS = 5
MAX_SUGGESTIONS = 2
MAX_PRAISE = 2

ANALYSIS_SYSTEM_PROMPT = f"""
You are an expert English language coach. You will receive ONE thing an English learner just SAID ALOUD.
It is a speech transcript: capitalisation, punctuation and spelling are artefacts of transcription, so NEVER mention them.

Give feedback as items in "corrections". There are three kinds:

1. MISTAKE — something wrong.                      "is_error": true,  "is_positive": false
{{mistake_subtypes}}
   Hints: "articles" = a missing, extra or wrong a/an/the (e.g. "she is teacher" -> "she is a teacher").
          "countable_uncountable" = an UNCOUNTABLE noun used as if it were countable (given a plural -s, or "a", "many"): "advices", "furnitures", "many homeworks"; or less/fewer and much/many mixed up: "less people".
          "wrong_collocation" = a wrong word partnership (e.g. "make a photo" -> "take a photo").
          "prepositions" = e.g. "depends of" -> "depends on", "arrive to" -> "arrive at".
2. SUGGESTION — correct, but a fluent speaker would say it differently or better.   "is_error": false, "is_positive": false
   category "naturalness": {", ".join(taxonomy.SUGGESTION_SUBTYPES)}
3. PRAISE — the learner used something genuinely natural or advanced, correctly:   "is_error": false, "is_positive": true
   category "naturalness": {", ".join(taxonomy.PRAISE_SUBTYPES)}
   - idiom_used: a figurative expression whose meaning is not its literal words ("a piece of cake", "break the ice", "under the weather").
   - phrasal_verb_used: a verb + particle with a special meaning ("figure out", "come up with", "put up with", "sort out").
   - good_collocation: a strong, natural word partnership ("make a decision", "heavy traffic", "reach a conclusion").
   - good_structure: a well-built longer sentence (relative clauses, conditionals, linking words).
   Ordinary words and phrases are NOT praise: "last week", "in the morning", "a lot of", "I think", "thank you", "for example".

Rules:
- Report EACH separate mistake as its own item with its own short quote. If the same kind of mistake happens twice with different words, report both.
- "original" MUST be an exact quote of a few of the words the learner said (the smallest span that shows the issue, never the whole turn). Never invent or paraphrase what they said.
- "correction" is the better wording and must differ from "original". For praise, repeat the learner's words.
- "explanation" is ONE short sentence a learner can understand. For praise, say what the expression means or why it is good.
- Use ONLY the subtype ids listed above, exactly as written.
- Be accurate, not exhaustive. Report only what you are confident about. If there is nothing worth saying, return {{"corrections": []}}.
- Give a SUGGESTION only when it clearly makes the English more natural — never for tiny additions ("just", "really") and never to replace an idiom or phrasal verb that was used correctly (that is praise).
- One item per underlying mistake: do not label the same words with two different subtypes.
- At most {MAX_ITEMS} items: mistakes first (most important first), then at most {MAX_SUGGESTIONS} suggestions, then at most {MAX_PRAISE} praise items.
- "severity": "high" for a basic error or one that could cause misunderstanding, "medium" for a typical error, "low" for minor issues. Suggestions and praise are always "low".
- A noun that is really uncountable but is made plural or given "a" is grammar/countable_uncountable, NOT vocabulary: the word exists, the grammar around it is what is wrong.
- Spoken English is informal: contractions, fragments and "gonna/wanna" are fine, not mistakes.

Return ONLY valid JSON in exactly this shape:
{{
  "corrections": [
    {{"category": "grammar", "subtype": "past_tense", "original": "I go to the mall yesterday", "correction": "I went to the mall yesterday",
      "explanation": "Use the simple past for finished actions.", "is_error": true, "is_positive": false, "severity": "high"}},
    {{"category": "naturalness", "subtype": "weak_vocabulary", "original": "it was very good", "correction": "it was excellent",
      "explanation": "A stronger word sounds more natural than 'very good'.", "is_error": false, "is_positive": false, "severity": "low"}},
    {{"category": "naturalness", "subtype": "idiom_used", "original": "a piece of cake", "correction": "a piece of cake",
      "explanation": "An idiom meaning 'very easy' — used correctly.", "is_error": false, "is_positive": true, "severity": "low"}}
  ]
}}
""".replace(
    "{mistake_subtypes}",
    "\n".join(f'   category "{c}": {", ".join(ids)}' for c, ids in taxonomy.MISTAKE_SUBTYPES.items()),
)


def _system_prompt_for(style: str) -> str:
    """Adds the variety-awareness clause for non-standard styles."""
    if style == DEFAULT_STYLE or style not in STYLES:
        return ANALYSIS_SYSTEM_PROMPT
    label = STYLES[style]["label"]
    return (
        ANALYSIS_SYSTEM_PROMPT.rstrip()
        + f"\n\nThe learner is practising {label}. Vocabulary, spelling and phrasing that is "
        "standard in that variety is CORRECT — never report it as an error. Only report genuine "
        "errors and natural-sounding improvements. If a different regional form is worth knowing, "
        'you may mention it as a suggestion with "is_error": false.\n'
    )


# ── Cleaning the model's output ───────────────────────────────────────────────

def _match_form(text: str) -> str:
    """Lower-cased, punctuation-free, single-spaced — the form two renderings of the same speech agree on."""
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def quoted_in(original: str, transcript: str) -> bool:
    """True if `original` really occurs in what the learner said (allowing for punctuation/case)."""
    needle = _match_form(original)
    return bool(needle) and needle in _match_form(transcript)


MAX_PRAISE_WORDS = 8  # praise points at an expression, not a whole sentence


def _is_noop(item: CorrectionItem) -> bool:
    """A 'correction' that changes nothing once punctuation and case are ignored (e.g. a comma swapped for a semicolon)."""
    return not item.is_positive and _match_form(item.correction) == _match_form(item.original)


def _kind_rank(item: CorrectionItem) -> int:
    return 2 if item.is_positive else (0 if item.is_error else 1)


def clean_items(raw_items: list, transcript: str) -> list[CorrectionItem]:
    """
    Validates, normalises, verifies, de-duplicates and limits the model's items.
    Order of the result: mistakes, then suggestions, then praise.
    """
    cleaned: list[CorrectionItem] = []
    seen: set[tuple[str, str]] = set()

    for raw in raw_items:
        try:
            item = CorrectionItem.model_validate(raw)
        except ValidationError as exc:
            logger.warning("Skipping malformed correction: %s", exc.errors()[0].get("msg", exc))
            continue

        item.subtype = taxonomy.normalise_subtype(item.category, item.subtype)
        if item.is_positive:
            # Praise always lives in naturalness with a praise subtype.
            item.category = "naturalness"
            if not taxonomy.is_praise_subtype(item.subtype):
                item.subtype = "good_structure"

        if not quoted_in(item.original, transcript):
            logger.warning("Dropping a correction whose quote isn't in the transcript: %r", item.original[:60])
            continue
        if _is_noop(item):
            logger.warning("Dropping a correction that changes nothing: %r", item.original[:60])
            continue
        if item.is_positive and not (2 <= len(item.original.split()) <= MAX_PRAISE_WORDS):
            logger.warning("Dropping praise that doesn't point at an expression: %r", item.original[:60])
            continue

        key = (item.subtype, _match_form(item.original))
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)

    cleaned.sort(key=_kind_rank)  # stable: the model's own priority is kept within each kind

    limited, suggestions, praise = [], 0, 0
    for item in cleaned:
        if item.is_positive:
            praise += 1
            if praise > MAX_PRAISE:
                continue
        elif not item.is_error:
            suggestions += 1
            if suggestions > MAX_SUGGESTIONS:
                continue
        limited.append(item)
    return limited[:MAX_ITEMS]


# ── The background task ───────────────────────────────────────────────────────

def _set_status(message_id: str, status: str) -> None:
    """Records how the analysis of a user turn ended (pending -> done | failed | skipped)."""
    try:
        with SessionLocal() as db:
            message = db.get(Message, message_id)
            if message is not None:
                message.analysis_status = status
                db.commit()
    except Exception:
        logger.exception("Could not record analysis status %r for message %s", status, message_id)


def run_async_analysis(
    transcript: str,
    message_id: str,
    conversation_id: str,
    user_id: str,
    style: str = DEFAULT_STYLE,
) -> None:
    """
    Background task to analyze a user's transcript and save corrections to the DB.
    `style` is the English variety the learner chose, so usage that is standard
    in that variety (e.g. British "queue"/"lift") is not flagged as a mistake.

    Always leaves the message's analysis_status at done / failed / skipped —
    never 'pending' — so the API (and session reports) can tell "feedback is
    still coming" from "there is none".
    """
    if not transcript or len(transcript.strip()) < 5:
        _set_status(message_id, "skipped")
        return

    try:
        messages = [
            {"role": "system", "content": _system_prompt_for(style)},
            {"role": "user", "content": transcript},
        ]
        raw = json.loads(llm.chat_json(messages))
    except Exception as exc:
        if llm.is_rate_limited(exc):
            logger.warning("Analysis not run: the LLM provider kept rate-limiting us, even after retrying")
        else:
            logger.exception("Analysis failed to get/parse the LLM response")
        _set_status(message_id, "failed")
        return

    raw_items = raw.get("corrections", []) if isinstance(raw, dict) else []
    items = clean_items(raw_items if isinstance(raw_items, list) else [], transcript)

    try:
        with SessionLocal() as db:
            for item in items:
                db.add(Correction(
                    message_id=message_id,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    category=item.category,
                    subtype=item.subtype,
                    original=item.original,
                    correction=item.correction,
                    explanation=item.explanation,
                    is_error=item.is_error,
                    is_positive=item.is_positive,
                    severity=item.severity,
                ))
            message = db.get(Message, message_id)
            if message is not None:
                message.analysis_status = "done"
            db.commit()
    except Exception:
        logger.exception("Failed to save corrections")
        _set_status(message_id, "failed")
