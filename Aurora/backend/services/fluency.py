"""
Fluency analysis — HOW a learner speaks, not what they say.

Pure functions over the word timings the speech recogniser returns: no I/O, no
database, no network, so every rule here is unit-tested and cheap to run on every
turn. The metrics are deliberately simple and explainable to a learner:

    speaking rate     words per minute across the time they were actually talking
    pauses            gaps in the middle of a thought (not between sentences)
    fillers           "um", "uh" and discourse fillers like "you know"
    repetitions       a word said twice in a row ("I I went")

Judgement calls worth knowing about:

  * A pause only counts if it interrupts a thought. A gap after a full stop is
    just a breath between sentences, and a short gap after a comma is normal
    phrasing — penalising those would mark fluent speech down.
  * "like", "you know", "kind of" are ordinary words too ("I like pizza", "what
    kind of music"), so they only count as fillers when the speaker set them off
    with commas, which is how speech recognisers transcribe the filler use.
  * Whether "um"/"uh" can be detected depends on the recogniser. Local
    faster-whisper base.en deletes them; hosted Whisper keeps them. The result
    says which (`hesitations_tracked`) so the UI never claims "0 fillers" when
    the truth is "couldn't hear them".
"""
import re
from dataclasses import dataclass, field

# ── Thresholds (seconds) ──────────────────────────────────────────────────────
PAUSE_SECONDS = 0.5            # a gap at least this long, mid-thought, is a pause
LONG_PAUSE_SECONDS = 1.5       # ...and this long is a long pause
CLAUSE_PAUSE_ALLOWANCE = 1.0   # after , ; : a gap shorter than this is normal phrasing
MIN_WORDS_FOR_RATE = 3         # a speaking rate over fewer words is meaningless
MIN_SPAN_FOR_RATE = 1.0        # ...as is one measured over under a second

_SENTENCE_END = (".", "?", "!", "…")
_CLAUSE_END = (",", ";", ":")

# Hesitation sounds, mapped to one canonical spelling for the breakdown. ("ah" and
# "huh" are left out on purpose: they are ordinary interjections, not hesitation.)
_HESITATION_FORMS = {
    "um": "um", "umm": "um", "uhm": "um",
    "uh": "uh", "uhh": "uh",
    "er": "er", "erm": "er",
    "hmm": "hmm", "hm": "hmm", "mm": "hmm", "mmm": "hmm",
}

# Discourse fillers that are also ordinary words: counted only when set off by commas.
_CONTEXTUAL_FILLERS = [("you", "know"), ("i", "mean"), ("sort", "of"), ("kind", "of"), ("like",)]
# Fillers that are (almost) never meaningful content when a learner says them.
_ALWAYS_FILLERS = {"basically"}
# Doubled words that are legitimate English, so they aren't "repetitions".
_REPEAT_ALLOWED = {"had", "that", "very", "really", "so", "no", "bye", "well"}


@dataclass
class FluencyMetrics:
    score: int
    word_count: int
    speech_seconds: float                 # first word start -> last word end
    wpm: float | None                     # None when there isn't enough speech to say
    articulation_wpm: float | None        # the same, with the pauses taken out
    pause_count: int
    long_pause_count: int
    total_pause_seconds: float
    longest_pause_seconds: float
    filler_count: int
    filler_breakdown: dict[str, int]
    repetition_count: int
    hesitations_tracked: bool
    events: list[dict] = field(default_factory=list)  # [{kind, start, end, text}] in time order

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "word_count": self.word_count,
            "speech_seconds": self.speech_seconds,
            "wpm": self.wpm,
            "articulation_wpm": self.articulation_wpm,
            "pause_count": self.pause_count,
            "long_pause_count": self.long_pause_count,
            "total_pause_seconds": self.total_pause_seconds,
            "longest_pause_seconds": self.longest_pause_seconds,
            "filler_count": self.filler_count,
            "filler_breakdown": self.filler_breakdown,
            "repetition_count": self.repetition_count,
            "hesitations_tracked": self.hesitations_tracked,
            "events": self.events,
        }


@dataclass
class _Token:
    raw: str
    norm: str
    start: float
    end: float


def _normalise(word: str) -> str:
    return re.sub(r"[^\w']", "", word.lower())


def _tokens(words: list[dict]) -> list[_Token]:
    out = []
    for w in words:
        raw = str(w.get("word", "")).strip()
        norm = _normalise(raw)
        if norm:
            out.append(_Token(raw=raw, norm=norm, start=float(w.get("start", 0.0)), end=float(w.get("end", 0.0))))
    return out


def _find_pauses(tokens: list[_Token]) -> list[dict]:
    pauses = []
    for prev, cur in zip(tokens, tokens[1:]):
        gap = cur.start - prev.end
        if gap < PAUSE_SECONDS:
            continue
        if prev.raw.endswith(_SENTENCE_END):
            continue                       # a breath between sentences
        if prev.raw.endswith(_CLAUSE_END) and gap < CLAUSE_PAUSE_ALLOWANCE:
            continue                       # normal phrasing
        pauses.append({
            "kind": "long_pause" if gap >= LONG_PAUSE_SECONDS else "pause",
            "start": round(prev.end, 2), "end": round(cur.start, 2), "text": f"{gap:.1f}s",
        })
    return pauses


def _find_fillers(tokens: list[_Token]) -> list[dict]:
    fillers = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if tok.norm in _HESITATION_FORMS:
            fillers.append({"kind": "filler", "start": round(tok.start, 2), "end": round(tok.end, 2), "text": _HESITATION_FORMS[tok.norm]})
            i += 1
            continue

        if tok.norm in _ALWAYS_FILLERS:
            fillers.append({"kind": "filler", "start": round(tok.start, 2), "end": round(tok.end, 2), "text": tok.norm})
            i += 1
            continue

        matched = False
        for phrase in _CONTEXTUAL_FILLERS:
            window = tokens[i:i + len(phrase)]
            if tuple(t.norm for t in window) != phrase:
                continue
            before_comma = i > 0 and tokens[i - 1].raw.endswith(_CLAUSE_END)
            after_comma = window[-1].raw.endswith(_CLAUSE_END)
            if before_comma or after_comma:
                fillers.append({
                    "kind": "filler", "start": round(window[0].start, 2), "end": round(window[-1].end, 2),
                    "text": " ".join(phrase),
                })
                i += len(phrase)
                matched = True
            break
        if not matched:
            i += 1
    return fillers


def _find_repetitions(tokens: list[_Token]) -> list[dict]:
    reps = []
    for prev, cur in zip(tokens, tokens[1:]):
        if (
            prev.norm == cur.norm
            and prev.norm not in _REPEAT_ALLOWED
            and prev.norm not in _HESITATION_FORMS
        ):
            reps.append({"kind": "repetition", "start": round(cur.start, 2), "end": round(cur.end, 2), "text": cur.norm})
    return reps


def compute_score(
    wpm: float | None,
    pause_count: int,
    long_pause_count: int,
    filler_count: int,
    repetition_count: int,
    word_count: int,
) -> int:
    """
    0-100, starting from 100 and subtracting for each problem. Every deduction is
    capped, so one bad habit can't zero the score and the result stays easy to
    explain ("-9 for three pauses").

        speaking rate   < 60 wpm -25 | < 80 -20 | < 100 -8 | 180-200 -3 | > 200 -10   (learners do best around 100-180)
        pauses          -3 each (max -20), plus -4 per long pause (max -12)
        fillers         -4 each (max -25)
        repetitions     -2 each (max -10)
        very short      -15 under 10 words (too little speech to be fluent in)
    """
    score = 100
    if wpm is not None:
        if wpm < 60:
            score -= 25
        elif wpm < 80:
            score -= 20
        elif wpm < 100:
            score -= 8
        elif wpm > 200:
            score -= 10
        elif wpm > 180:
            score -= 3
    score -= min(pause_count * 3, 20)
    score -= min(long_pause_count * 4, 12)
    score -= min(filler_count * 4, 25)
    score -= min(repetition_count * 2, 10)
    if word_count < 10:
        score -= 15
    return max(0, min(100, score))


def analyse(words: list[dict], hesitations_tracked: bool = False) -> FluencyMetrics:
    """
    Fluency metrics for one spoken turn.

    Args:
        words: [{word, start, end, ...}, ...] in time order, as stored on the message.
        hesitations_tracked: whether the recogniser keeps "um"/"uh" (see stt.supports_fillers()).
    """
    tokens = _tokens(words)
    hesitation_tokens = sum(1 for t in tokens if t.norm in _HESITATION_FORMS)
    word_count = len(tokens) - hesitation_tokens

    if not tokens or word_count == 0:
        return FluencyMetrics(
            score=compute_score(None, 0, 0, 0, 0, 0), word_count=0, speech_seconds=0.0, wpm=None,
            articulation_wpm=None, pause_count=0, long_pause_count=0, total_pause_seconds=0.0,
            longest_pause_seconds=0.0, filler_count=0, filler_breakdown={}, repetition_count=0,
            hesitations_tracked=hesitations_tracked,
        )

    pauses = _find_pauses(tokens)
    fillers = _find_fillers(tokens)
    repetitions = _find_repetitions(tokens)

    span = max(0.0, tokens[-1].end - tokens[0].start)
    pause_durations = [p["end"] - p["start"] for p in pauses]
    total_pause = round(sum(pause_durations), 2)
    longest = round(max(pause_durations), 2) if pause_durations else 0.0

    wpm = round(word_count / span * 60, 1) if word_count >= MIN_WORDS_FOR_RATE and span >= MIN_SPAN_FOR_RATE else None
    moving = span - total_pause
    articulation = round(word_count / moving * 60, 1) if wpm is not None and moving >= MIN_SPAN_FOR_RATE else None

    breakdown: dict[str, int] = {}
    for f in fillers:
        breakdown[f["text"]] = breakdown.get(f["text"], 0) + 1

    long_count = sum(1 for p in pauses if p["kind"] == "long_pause")
    return FluencyMetrics(
        score=compute_score(wpm, len(pauses), long_count, len(fillers), len(repetitions), word_count),
        word_count=word_count,
        speech_seconds=round(span, 2),
        wpm=wpm,
        articulation_wpm=articulation,
        pause_count=len(pauses),
        long_pause_count=long_count,
        total_pause_seconds=total_pause,
        longest_pause_seconds=longest,
        filler_count=len(fillers),
        filler_breakdown=dict(sorted(breakdown.items(), key=lambda kv: -kv[1])),
        repetition_count=len(repetitions),
        hesitations_tracked=hesitations_tracked,
        events=sorted(pauses + fillers + repetitions, key=lambda e: (e["start"], e["end"])),
    )
