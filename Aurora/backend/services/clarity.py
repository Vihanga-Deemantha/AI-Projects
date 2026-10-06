"""
Clarity — how confidently speech recognition identified what the learner said.

This is an ESTIMATE, and the product says so. Whisper reports a confidence for
every word it transcribes. When someone's pronunciation is unclear (or the
audio is muffled, or they said a different word than they meant), those
confidences drop on exactly the affected words — measured here: muffling a clip
took "near" to 0.08 and made the recogniser hear "library" as "lobby" at 0.24,
while clean speech sat at 0.96-0.98 throughout. That makes it a useful pointer
to words worth practising. It is NOT phoneme-level pronunciation analysis: a
low score can also mean background noise, an unusual word, or a mis-heard
homophone, and a high one doesn't prove native-like sounds.

Two signals, used when available:

  word level     per-word probabilities (local faster-whisper provides them):
                 the score and the list of "hard to catch" words.
  segment level  only the average log-probability (the hosted Whisper API gives
                 no per-word confidence): a rougher score and no word list.

Pure functions: no I/O, fully unit-tested.
"""
import math
import re
from dataclasses import dataclass, field

UNCLEAR_BELOW = 0.80          # a word recognised with less confidence than this is "hard to catch"
CONFIDENT_AT = 0.80           # ...and one at or above this counts as confidently recognised
MAX_UNCLEAR_WORDS = 5         # the list stays short enough to act on
MIN_UNCLEAR_WORD_LEN = 3      # "a", "to", "it" are low-confidence all the time and nothing to practise
MEAN_WEIGHT = 0.6             # score = 60% mean confidence + 40% share of confidently recognised words

# Segment-level fallback: exp(avg_logprob) is ~0.78 even for perfectly clean audio
# (it's measured per sub-word token, punctuation included), so it can't be shown as
# a percentage directly. This stretches the realistic range [0.40, 0.85] onto 0-100.
_FALLBACK_FLOOR = 0.40
_FALLBACK_SPAN = 0.45

_HESITATIONS = {"um", "umm", "uhm", "uh", "uhh", "er", "erm", "hmm", "hm", "mm", "mmm"}

# Very common function words. Speech recognisers are routinely unsure about these
# (they're short, unstressed and run together) and nobody needs to practise "the",
# so they never appear in the "hard to catch" list. They still count toward the score.
_FUNCTION_WORDS = frozenset("""
    the and for are but not you she her him his was has had can may our its who how why did too any all
    with that this have from they them were what when will your been than then into also just about would
    could should there their which while where these those some such very much more most only over under
    does done each both other another being because
""".split())


@dataclass
class ClarityMetrics:
    score: int                              # 0-100
    word_level: bool                        # False = rough estimate from segment confidence only
    avg_word_confidence: float | None
    avg_logprob: float
    words_scored: int
    unclear_words: list[dict] = field(default_factory=list)   # [{word, probability, start, end}], least clear first

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "word_level": self.word_level,
            "avg_word_confidence": self.avg_word_confidence,
            "avg_logprob": self.avg_logprob,
            "words_scored": self.words_scored,
            "unclear_words": self.unclear_words,
        }


def _bare(word: str) -> str:
    return re.sub(r"[^A-Za-z']", "", word)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_from_word_confidences(confidences: list[float]) -> int:
    """60% mean confidence + 40% share of words recognised confidently, as 0-100."""
    if not confidences:
        return 0
    mean = sum(confidences) / len(confidences)
    confident_share = sum(1 for c in confidences if c >= CONFIDENT_AT) / len(confidences)
    return round(100 * _clamp(MEAN_WEIGHT * mean + (1 - MEAN_WEIGHT) * confident_share))


def score_from_logprob(avg_logprob: float) -> int:
    """The rough segment-level score (see _FALLBACK_*)."""
    return round(100 * _clamp((math.exp(avg_logprob) - _FALLBACK_FLOOR) / _FALLBACK_SPAN))


def analyse(words: list[dict], avg_logprob: float) -> ClarityMetrics | None:
    """
    Clarity for one spoken turn, or None if there was nothing to score.

    Args:
        words:       [{word, start, end, probability|None}, ...] from the recogniser.
        avg_logprob: the recogniser's average log-probability for the turn.
    """
    spoken = [w for w in words if _bare(str(w.get("word", ""))) and _bare(str(w.get("word", ""))).lower() not in _HESITATIONS]
    if not spoken:
        return None

    with_confidence = [w for w in spoken if w.get("probability") is not None]
    if not with_confidence:
        return ClarityMetrics(
            score=score_from_logprob(avg_logprob), word_level=False, avg_word_confidence=None,
            avg_logprob=round(float(avg_logprob), 4), words_scored=len(spoken),
        )

    confidences = [float(w["probability"]) for w in with_confidence]
    unclear = sorted(
        (
            w for w in with_confidence
            if float(w["probability"]) < UNCLEAR_BELOW
            and len(_bare(str(w["word"]))) >= MIN_UNCLEAR_WORD_LEN
            and _bare(str(w["word"])).lower() not in _FUNCTION_WORDS
        ),
        key=lambda w: float(w["probability"]),
    )[:MAX_UNCLEAR_WORDS]

    return ClarityMetrics(
        score=score_from_word_confidences(confidences),
        word_level=True,
        avg_word_confidence=round(sum(confidences) / len(confidences), 3),
        avg_logprob=round(float(avg_logprob), 4),
        words_scored=len(confidences),
        unclear_words=[
            {
                "word": re.sub(r"^[^\w']+|[^\w']+$", "", str(w["word"])),
                "probability": round(float(w["probability"]), 3),
                "start": round(float(w.get("start", 0.0)), 2),
                "end": round(float(w.get("end", 0.0)), 2),
            }
            for w in unclear
        ],
    )
