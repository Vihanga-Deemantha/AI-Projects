"""
Speech metrics for one spoken turn: compute (pure) -> store (database) -> serialise.

The maths lives in services/fluency.py and services/clarity.py; this module is
the glue the voice endpoint and the history endpoints share, so a metric is
computed once, saved with the turn, and rendered the same way everywhere.

The metrics are independent: if one fails to compute the other is still
returned, and if all fail the learner's turn carries on without them.
"""
import logging

from sqlalchemy.orm import Session

from backend.models.metrics import ClarityScore, FluencyEvent, FluencyScore
from backend.services import clarity, fluency, stt

logger = logging.getLogger("aura.metrics")


def analyse(stt_result: dict) -> dict | None:
    """
    Computes every metric for a transcribed turn:
        {"fluency": FluencyMetrics, "clarity": ClarityMetrics}   (each present only if computable)
    Returns None if nothing could be computed.
    """
    metrics: dict = {}
    try:
        metrics["fluency"] = fluency.analyse(stt_result["words"], hesitations_tracked=stt.supports_fillers())
    except Exception:
        logger.exception("Computing fluency failed; continuing without it")
    try:
        result = clarity.analyse(stt_result["words"], stt_result["avg_logprob"])
        if result is not None:
            metrics["clarity"] = result
    except Exception:
        logger.exception("Computing clarity failed; continuing without it")
    return metrics or None


def save(db: Session, *, message_id: str, user_id: str, conversation_id: str, metrics: dict) -> None:
    """Adds the metric rows for a message to `db` (the caller commits, in the same transaction as the message)."""
    f: fluency.FluencyMetrics | None = metrics.get("fluency")
    if f is not None:
        row = FluencyScore(
            message_id=message_id, user_id=user_id, conversation_id=conversation_id,
            score=f.score, word_count=f.word_count, speech_seconds=f.speech_seconds,
            wpm=f.wpm, articulation_wpm=f.articulation_wpm,
            pause_count=f.pause_count, long_pause_count=f.long_pause_count,
            total_pause_seconds=f.total_pause_seconds, longest_pause_seconds=f.longest_pause_seconds,
            filler_count=f.filler_count, filler_breakdown=f.filler_breakdown,
            repetition_count=f.repetition_count, hesitations_tracked=f.hesitations_tracked,
        )
        db.add(row)
        db.flush()  # need row.id for the events
        for event in f.events:
            db.add(FluencyEvent(
                fluency_score_id=row.id, user_id=user_id, kind=event["kind"], text=str(event["text"])[:100],
                start_seconds=event["start"], end_seconds=event["end"],
            ))

    c: clarity.ClarityMetrics | None = metrics.get("clarity")
    if c is not None:
        db.add(ClarityScore(
            message_id=message_id, user_id=user_id, conversation_id=conversation_id,
            score=c.score, word_level=c.word_level, avg_word_confidence=c.avg_word_confidence,
            avg_logprob=c.avg_logprob, words_scored=c.words_scored, unclear_words=c.unclear_words,
        ))


def to_payload(metrics: dict | None) -> dict:
    """The JSON the stream's `metrics` event sends for freshly computed metrics."""
    metrics = metrics or {}
    return {
        "fluency": metrics["fluency"].to_dict() if "fluency" in metrics else None,
        "clarity": metrics["clarity"].to_dict() if "clarity" in metrics else None,
    }


def fluency_row_to_dict(row: FluencyScore) -> dict:
    """The same shape as FluencyMetrics.to_dict(), from a stored row."""
    return {
        "score": row.score,
        "word_count": row.word_count,
        "speech_seconds": row.speech_seconds,
        "wpm": row.wpm,
        "articulation_wpm": row.articulation_wpm,
        "pause_count": row.pause_count,
        "long_pause_count": row.long_pause_count,
        "total_pause_seconds": row.total_pause_seconds,
        "longest_pause_seconds": row.longest_pause_seconds,
        "filler_count": row.filler_count,
        "filler_breakdown": row.filler_breakdown or {},
        "repetition_count": row.repetition_count,
        "hesitations_tracked": row.hesitations_tracked,
        "events": [
            {"kind": e.kind, "start": e.start_seconds, "end": e.end_seconds, "text": e.text}
            for e in row.events
        ],
    }


def clarity_row_to_dict(row: ClarityScore) -> dict:
    """The same shape as ClarityMetrics.to_dict(), from a stored row."""
    return {
        "score": row.score,
        "word_level": row.word_level,
        "avg_word_confidence": row.avg_word_confidence,
        "avg_logprob": row.avg_logprob,
        "words_scored": row.words_scored,
        "unclear_words": row.unclear_words or [],
    }
