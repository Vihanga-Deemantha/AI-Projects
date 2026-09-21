import json
from pydantic import ValidationError

from backend.services.llm import chat_json
from backend.database import SessionLocal
from backend.models.core import Correction
from backend.schemas.core import CorrectionItem
from backend.personalities import DEFAULT_STYLE, STYLES

ANALYSIS_SYSTEM_PROMPT = """
You are a professional English language analyst. Analyze the user's speech for:
- Grammar errors (incorrect tense, articles, prepositions, subject-verb agreement)  
- Vocabulary issues (repetitive words, wrong collocations, awkward phrasing)
- Naturalness suggestions (grammatically correct but unnatural expressions)

Return ONLY valid JSON in this exact format:
{
  "corrections": [
    {
      "category": "grammar",
      "subtype": "past_tense",
      "original": "I go to mall yesterday",
      "correction": "I went to the mall yesterday",
      "explanation": "Use simple past tense for completed past actions.",
      "is_error": true,
      "severity": "high"
    }
  ]
}

Categories MUST be one of: "grammar", "vocabulary", "naturalness".
If there are no errors or suggestions, return {"corrections": []}.
Output valid JSON and nothing else.
"""

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


def run_async_analysis(
    transcript: str,
    message_id: str,
    conversation_id: str,
    user_id: str,
    style: str = DEFAULT_STYLE,
):
    """
    Background task to analyze a user's transcript and save corrections to the DB.
    `style` is the English variety the learner chose, so usage that is standard
    in that variety (e.g. British "queue"/"lift") is not flagged as a mistake.
    """
    if not transcript or len(transcript.strip()) < 5:
        return

    try:
        messages = [
            {"role": "system", "content": _system_prompt_for(style)},
            {"role": "user", "content": transcript}
        ]
        json_str = chat_json(messages)
        raw = json.loads(json_str)
    except Exception as e:
        print(f"[Analysis Error] Failed to get/parse LLM response: {e}")
        return

    # Validate each item individually so one malformed entry (e.g. an invalid
    # category/severity the LLM hallucinated) doesn't discard the whole batch.
    raw_items = raw.get("corrections", []) if isinstance(raw, dict) else []
    validated: list[CorrectionItem] = []
    for item in raw_items:
        try:
            validated.append(CorrectionItem.model_validate(item))
        except ValidationError as e:
            print(f"[Analysis Warning] Skipping malformed correction: {e}")

    if not validated:
        return

    try:
        with SessionLocal() as db:
            for item in validated:
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
                    severity=item.severity,
                ))
            db.commit()
    except Exception as e:
        print(f"[Analysis Error] Failed to save corrections: {e}")
