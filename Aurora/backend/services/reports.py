"""
Session reports: generate one per finished session, read it back, serialise it.

The scores and the strengths/improvements text are computed deterministically
from the session's stored feedback (services/scoring.py) — the same session
always gets the same report, and it is unit-tested. The LLM is used only for the
short personal note at the top, and a failure there just leaves the note out.

Reports are generated in the background when a session ends, but a learner can
open the report page at any moment — so `generate_report` is safe to call from
anywhere, any number of times: there is one report per session. Calls for the same
session take turns inside the process (the second one finds the first one's report
instead of paying for a second LLM note), and a unique key is the net underneath for
anything that slips past, such as another worker process: whoever loses that race
simply reads the winner's report.
"""
import json
import logging
import threading
import time
from contextlib import contextmanager

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import taxonomy
from backend.config import LLM_ANALYSIS_MODEL
from backend.database import SessionLocal
from backend.models.core import Conversation, Correction, Message
from backend.models.metrics import ClarityScore, FluencyScore
from backend.models.reports import SessionReport
from backend.services import llm, scoring, weaknesses
from backend.services.turns import count_pending_analysis

logger = logging.getLogger("aura.reports")

# The last turn's analysis is still running when a session ends; the report waits
# for it (up to this long) so its last mistakes aren't missing from the score.
WAIT_FOR_ANALYSIS_SECONDS = 25.0
_POLL_SECONDS = 0.5

_LABELS = {(c, s): info["label"] for c, subs in taxonomy.SUBTYPES.items() for s, info in subs.items()}

_guard = threading.Lock()
_in_progress: dict[str, list] = {}      # conversation id -> [lock, how many callers hold or wait for it]


@contextmanager
def _one_at_a_time(conversation_id: str):
    """
    Callers for the same session take turns; different sessions don't wait for each other. The entry is
    forgotten once nobody holds or waits for it, so the table can't grow without bound.
    """
    with _guard:
        entry = _in_progress.setdefault(conversation_id, [threading.Lock(), 0])
        entry[1] += 1
    try:
        with entry[0]:
            yield
    finally:
        with _guard:
            entry[1] -= 1
            if entry[1] == 0:
                del _in_progress[conversation_id]


def _correction_dict(c: Correction) -> dict:
    return {
        "category": c.category, "subtype": c.subtype, "severity": c.severity,
        "original": c.original, "correction": c.correction,
    }


def gather_evidence(db: Session, conversation_id: str) -> tuple[scoring.Evidence, int, int]:
    """Collects everything the scores are computed from. Returns (evidence, user_turns, total_words)."""
    user_msgs = db.query(Message).filter(Message.conversation_id == conversation_id, Message.role == "user").all()
    total_words = sum(len(m.content.split()) for m in user_msgs)
    analysed = [m for m in user_msgs if m.analysis_status == "done"]

    corrections = db.query(Correction).filter(Correction.conversation_id == conversation_id).all()
    mistakes = [_correction_dict(c) for c in corrections if c.is_error and not c.is_positive]
    suggestions = [_correction_dict(c) for c in corrections if not c.is_error and not c.is_positive]
    praise = [_correction_dict(c) for c in corrections if c.is_positive]

    fluency_rows = db.query(FluencyScore).filter(FluencyScore.conversation_id == conversation_id).all()
    breakdown: dict[str, int] = {}
    for row in fluency_rows:
        for word, n in (row.filler_breakdown or {}).items():
            breakdown[word] = breakdown.get(word, 0) + n

    unclear: dict[str, int] = {}
    clarity_rows = db.query(ClarityScore).filter(ClarityScore.conversation_id == conversation_id).all()
    for row in clarity_rows:
        for w in row.unclear_words or []:
            key = str(w.get("word", "")).lower()
            if key:
                unclear[key] = unclear.get(key, 0) + 1

    # Sessions from before analysis and speech metrics existed have no corrections
    # AND no metrics. "No mistakes" there means "never analysed", not "perfect", so
    # they must not be scored as flawless: with no evidence, the analysis-based
    # dimensions stay unknown.
    if not corrections and not fluency_rows and not clarity_rows:
        analysed = []

    evidence = scoring.Evidence(
        words_analysed=sum(len(m.content.split()) for m in analysed),
        analysed_turns=len(analysed),
        mistakes=mistakes, suggestions=suggestions, praise=praise,
        fluency_scores=[r.score for r in fluency_rows],
        clarity_scores=[r.score for r in clarity_rows],
        wpm_values=[r.wpm for r in fluency_rows if r.wpm is not None],
        filler_total=sum(r.filler_count for r in fluency_rows),
        filler_breakdown=breakdown,
        long_pause_total=sum(r.long_pause_count for r in fluency_rows),
        unclear_words=unclear,
        total_words=total_words,
    )
    return evidence, len(user_msgs), total_words


_SUMMARY_SYSTEM = (
    "You are AURA, a warm, encouraging English speaking coach. Write a short note (two sentences, at most "
    "45 words) to the learner about the practice session described below. Be specific: mention one real "
    "strength and one thing to work on next. Plain text only — no lists, headings, quotes or emojis. "
    "Speak to the learner as 'you'."
)


def _write_summary(facts: dict) -> str | None:
    """A personal note from the LLM. Best effort: any failure just means no note."""
    try:
        text = llm.chat(
            [{"role": "system", "content": _SUMMARY_SYSTEM}, {"role": "user", "content": json.dumps(facts)}],
            model=LLM_ANALYSIS_MODEL, temperature=0.6, max_tokens=500,
        )
    except Exception:
        logger.exception("Could not write the report summary")
        return None
    text = (text or "").strip().strip('"“”').strip()
    return text[:500] if len(text) >= 15 else None


def wait_for_analysis(conversation_id: str, timeout: float = WAIT_FOR_ANALYSIS_SECONDS) -> bool:
    """Blocks until no turn is still being analysed (True) or the timeout passes (False)."""
    deadline = time.monotonic() + timeout
    while True:
        with SessionLocal() as db:
            if count_pending_analysis(db, conversation_id) == 0:
                return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_POLL_SECONDS)


def get_report(db: Session, conversation_id: str) -> SessionReport | None:
    return db.query(SessionReport).filter(SessionReport.conversation_id == conversation_id).first()


def generate_report(
    conversation_id: str, wait_seconds: float = 0.0, with_summary: bool = True, refresh_weaknesses: bool = True
) -> dict | None:
    """
    Creates the report for a session if it doesn't exist yet, and returns it as a dict
    (None if the session has no spoken turns to report on).

    `wait_seconds` is how long to let in-flight analysis finish first. `with_summary`
    False skips the LLM note (used when back-filling many old sessions at once);
    `refresh_weaknesses` False skips rebuilding the weakness profile (the back-fill does that once at the end).
    """
    if wait_seconds > 0:
        wait_for_analysis(conversation_id, wait_seconds)

    # The end-of-session task and a learner opening the page can arrive together: whoever comes second waits
    # here, then finds the first one's report below, rather than writing the LLM note a second time.
    with _one_at_a_time(conversation_id), SessionLocal() as db:
        existing = get_report(db, conversation_id)
        if existing:
            return report_to_dict(existing)

        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            return None
        evidence, turns, total_words = gather_evidence(db, conversation_id)
        if turns == 0:
            return None

        content = scoring.build_report(evidence, _LABELS)
        practice_words = [w for w, _ in sorted(evidence.unclear_words.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]
        avg_wpm = round(sum(evidence.wpm_values) / len(evidence.wpm_values), 1) if evidence.wpm_values else None
        duration = (
            round((conversation.ended_at - conversation.started_at).total_seconds(), 1)
            if conversation.ended_at else None
        )
        summary = _write_summary({
            "scores": content.scores, "strengths": content.strengths, "improvements": content.improvements,
            "turns": turns, "words": total_words, "scenario": conversation.scenario,
        }) if with_summary and content.scores.get("overall") is not None else None

        report = SessionReport(
            conversation_id=conversation_id, user_id=conversation.user_id, scoring_version=scoring.SCORING_VERSION,
            overall_score=content.scores["overall"], grammar_score=content.scores["grammar"],
            vocabulary_score=content.scores["vocabulary"], fluency_score=content.scores["fluency"],
            clarity_score=content.scores["clarity"], naturalness_score=content.scores["naturalness"],
            strengths=content.strengths, improvements=content.improvements, top_errors=content.top_errors,
            practice_words=practice_words, summary=summary,
            total_turns=turns, total_words=total_words, duration_seconds=duration,
            mistake_count=len(evidence.mistakes), suggestion_count=len(evidence.suggestions),
            praise_count=len(evidence.praise), avg_wpm=avg_wpm, filler_count=evidence.filler_total,
        )
        db.add(report)
        conversation.overall_score = content.scores["overall"]
        try:
            db.commit()
        except IntegrityError:
            # Someone generated it a moment ago (the end-of-session task vs. a learner
            # opening the page). There is one report per session: read theirs.
            db.rollback()
            winner = get_report(db, conversation_id)
            return report_to_dict(winner) if winner else None
        db.refresh(report)
        if refresh_weaknesses:
            _refresh_weaknesses(db, conversation.user_id)
        return report_to_dict(report)


def _refresh_weaknesses(db: Session, user_id: str) -> None:
    """The weakness profile follows the reports. Never lets a profiling bug break a report."""
    try:
        weaknesses.recompute(db, user_id)
    except Exception:
        db.rollback()
        logger.exception("Refreshing the weakness profile for %s failed", user_id)


def backfill_missing(user_id: str, limit: int = 25) -> int:
    """
    Reports for finished sessions that don't have one (sessions from before reports
    existed). Newest first, at most `limit` per call, no LLM note — so the progress
    page can fill its history on first visit without a burst of LLM calls.
    Returns how many were created.
    """
    with SessionLocal() as db:
        missing = db.execute(
            select(Conversation.id)
            .where(
                Conversation.user_id == user_id,
                Conversation.is_complete.is_(True),
                ~exists().where(SessionReport.conversation_id == Conversation.id),
                exists().where(Message.conversation_id == Conversation.id, Message.role == "user"),
            )
            .order_by(Conversation.ended_at.desc())
            .limit(limit)
        ).scalars().all()

    created = 0
    for conversation_id in missing:
        try:
            if generate_report(conversation_id, with_summary=False, refresh_weaknesses=False):
                created += 1
        except Exception:
            logger.exception("Back-filling the report for %s failed", conversation_id)
    if created:
        with SessionLocal() as db:
            _refresh_weaknesses(db, user_id)
    return created


def generate_report_safely(conversation_id: str) -> None:
    """Background-task entry point: waits for analysis, then generates; never raises."""
    try:
        generate_report(conversation_id, wait_seconds=WAIT_FOR_ANALYSIS_SECONDS)
    except Exception:
        logger.exception("Generating the report for conversation %s failed", conversation_id)


def report_to_dict(r: SessionReport) -> dict:
    return {
        "id": r.id,
        "conversation_id": r.conversation_id,
        "generated_at": r.generated_at.isoformat(),
        "scoring_version": r.scoring_version,
        "scores": {
            "overall": r.overall_score,
            "grammar": r.grammar_score,
            "vocabulary": r.vocabulary_score,
            "fluency": r.fluency_score,
            "clarity": r.clarity_score,
            "naturalness": r.naturalness_score,
        },
        "strengths": r.strengths or [],
        "improvements": r.improvements or [],
        "top_errors": r.top_errors or [],
        "practice_words": r.practice_words or [],
        "summary": r.summary,
        "facts": {
            "turns": r.total_turns,
            "words": r.total_words,
            "duration_seconds": r.duration_seconds,
            "mistakes": r.mistake_count,
            "suggestions": r.suggestion_count,
            "praise": r.praise_count,
            "avg_wpm": r.avg_wpm,
            "fillers": r.filler_count,
        },
    }
