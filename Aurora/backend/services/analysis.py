import json
from pydantic import ValidationError

from backend.services.llm import chat_json
from backend.database import SessionLocal
from backend.models.core import Correction
from backend.schemas.core import CorrectionItem

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

def run_async_analysis(transcript: str, message_id: str, conversation_id: str, user_id: str):
    """
    Background task to analyze a user's transcript and save corrections to the DB.
    """
    if not transcript or len(transcript.strip()) < 5:
        return

    try:
        messages = [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
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
