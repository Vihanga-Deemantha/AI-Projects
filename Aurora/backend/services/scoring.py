"""
Session scoring — turns a session's raw feedback into five scores and a report's
words. Pure functions (no I/O), so every rule is unit-tested, and every constant
is here in one place: **changing a formula changes what people's progress charts
mean**, so bump SCORING_VERSION when you do (reports store the version they were
scored with, which also tells you which old reports to recompute).

Design rules:

  * Scores are DENSITIES, not counts: mistakes per 100 words, so a long, brave
    answer isn't punished for having more words in which to slip.
  * A short answer can't swing a score wildly: densities never divide by fewer
    than MIN_WORDS words.
  * A dimension with no evidence is None, never a flattering 100 (if every turn's
    analysis failed, "0 mistakes" would be a lie).
  * The overall score averages only the dimensions that have evidence.
"""
from dataclasses import dataclass, field

SCORING_VERSION = 1

# How much each dimension counts toward the overall score.
WEIGHTS = {"grammar": 0.30, "fluency": 0.25, "vocabulary": 0.15, "clarity": 0.15, "naturalness": 0.15}

# A mistake's weight by severity.
SEVERITY_WEIGHT = {"high": 1.5, "medium": 1.0, "low": 0.5}

MIN_WORDS = 15              # a density is never computed over fewer words than this
GRAMMAR_SLOPE = 4.0         # points lost per weighted grammar mistake per 100 words
VOCABULARY_SLOPE = 5.0      # ... per weighted vocabulary mistake per 100 words
NATURALNESS_BASE = 90.0     # a session with nothing to suggest sits here, so praise can lift it
SUGGESTION_SLOPE = 3.0      # points lost per suggestion per 100 words
PRAISE_BONUS = 5.0          # points gained per piece of praise...
PRAISE_BONUS_CAP = 20.0     # ...up to this much

STRONG_AT = 85              # a dimension this high is a strength
FILLER_RATE_TO_FLAG = 1 / 20  # one filler every 20 words is worth working on


def _clamp(value: float) -> int:
    return round(max(0.0, min(100.0, value)))


@dataclass
class Evidence:
    """Everything the scores are computed from, gathered from the database by services/reports.py."""
    words_analysed: int                       # words in the turns whose analysis finished
    analysed_turns: int
    mistakes: list[dict]                      # [{category, subtype, severity, original, correction}]
    suggestions: list[dict]
    praise: list[dict]
    fluency_scores: list[int] = field(default_factory=list)
    clarity_scores: list[int] = field(default_factory=list)
    wpm_values: list[float] = field(default_factory=list)
    filler_total: int = 0
    filler_breakdown: dict[str, int] = field(default_factory=dict)
    long_pause_total: int = 0
    unclear_words: dict[str, int] = field(default_factory=dict)   # word -> how many turns it was hard to catch in
    total_words: int = 0


def _density(weighted_count: float, words: int) -> float:
    return weighted_count / max(words, MIN_WORDS) * 100


def _weighted(items: list[dict]) -> float:
    return sum(SEVERITY_WEIGHT.get(i.get("severity", "medium"), 1.0) for i in items)


def mean_score(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


def compute_scores(e: Evidence) -> dict[str, int | None]:
    """The five dimension scores plus `overall` (any may be None when there is no evidence)."""
    scores: dict[str, int | None] = {"grammar": None, "vocabulary": None, "naturalness": None}

    if e.analysed_turns > 0:
        grammar_errors = [m for m in e.mistakes if m["category"] == "grammar"]
        vocab_errors = [m for m in e.mistakes if m["category"] == "vocabulary"]
        scores["grammar"] = _clamp(100 - GRAMMAR_SLOPE * _density(_weighted(grammar_errors), e.words_analysed))
        scores["vocabulary"] = _clamp(100 - VOCABULARY_SLOPE * _density(_weighted(vocab_errors), e.words_analysed))
        scores["naturalness"] = _clamp(
            NATURALNESS_BASE
            - SUGGESTION_SLOPE * _density(len(e.suggestions), e.words_analysed)
            + min(PRAISE_BONUS * len(e.praise), PRAISE_BONUS_CAP)
        )

    scores["fluency"] = mean_score(e.fluency_scores)
    scores["clarity"] = mean_score(e.clarity_scores)

    available = {k: v for k, v in scores.items() if v is not None}
    total_weight = sum(WEIGHTS[k] for k in available)
    scores["overall"] = (
        round(sum(WEIGHTS[k] * v for k, v in available.items()) / total_weight) if total_weight else None
    )
    return scores


# ── What the learner should read ──────────────────────────────────────────────

_STRONG_TEXT = {
    "grammar": "Accurate grammar",
    "vocabulary": "Precise word choice",
    "fluency": "Fluent, steady delivery",
    "clarity": "Clear speech that is easy to recognise",
    "naturalness": "Natural-sounding phrasing",
}


def top_errors(mistakes: list[dict], labels: dict[tuple[str, str], str], limit: int = 5) -> list[dict]:
    """The most frequent kinds of mistake, each with one example. Ordered by weighted count."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for m in mistakes:
        groups.setdefault((m["category"], m["subtype"]), []).append(m)
    ranked = sorted(groups.items(), key=lambda kv: (-_weighted(kv[1]), -len(kv[1]), kv[0]))
    return [
        {
            "category": category,
            "subtype": subtype,
            "label": labels.get((category, subtype), subtype.replace("_", " ").capitalize()),
            "count": len(items),
            "example_original": items[0]["original"],
            "example_correction": items[0]["correction"],
        }
        for (category, subtype), items in ranked[:limit]
    ]


def build_strengths(e: Evidence, scores: dict[str, int | None], labels: dict[tuple[str, str], str]) -> list[str]:
    strengths: list[str] = []

    praised: dict[str, list[str]] = {}
    for p in e.praise:
        praised.setdefault(labels.get((p["category"], p["subtype"]), "Good English"), []).append(p["original"])
    for label, quotes in sorted(praised.items(), key=lambda kv: -len(kv[1])):
        shown = ", ".join(f"“{q}”" for q in quotes[:2])
        strengths.append(f"Good use of {label.lower()}: {shown}")

    if e.analysed_turns >= 2 and not e.mistakes:
        strengths.append("No grammar or vocabulary mistakes this session")

    if e.wpm_values:
        wpm = sum(e.wpm_values) / len(e.wpm_values)
        if 110 <= wpm <= 170:
            strengths.append(f"A comfortable speaking pace ({round(wpm)} words per minute)")

    for dimension, text in _STRONG_TEXT.items():
        score = scores.get(dimension)
        if score is not None and score >= STRONG_AT and not any(text.lower() in s.lower() for s in strengths):
            if dimension == "grammar" and e.analysed_turns >= 2 and not e.mistakes:
                continue  # already said above
            strengths.append(text)

    return strengths[:3]


def build_improvements(e: Evidence, scores: dict[str, int | None], errors: list[dict]) -> list[str]:
    items: list[str] = []

    for err in errors[:2]:
        plural = "mistake" if err["count"] == 1 else "mistakes"
        items.append(f"{err['label']} — {err['count']} {plural} (e.g. “{err['example_original']}” → “{err['example_correction']}”)")

    if e.filler_total and e.total_words and e.filler_total / e.total_words >= FILLER_RATE_TO_FLAG:
        listing = ", ".join(f"{w} ×{n}" for w, n in sorted(e.filler_breakdown.items(), key=lambda kv: -kv[1])[:3])
        items.append(f"Cut down on filler words ({listing})")
    elif e.long_pause_total >= 2:
        items.append("Try to avoid long pauses in the middle of a sentence")

    if e.wpm_values:
        wpm = sum(e.wpm_values) / len(e.wpm_values)
        if wpm < 90:
            items.append(f"Speak a little faster — you averaged {round(wpm)} words per minute")
        elif wpm > 185:
            items.append(f"Slow down slightly — you averaged {round(wpm)} words per minute")

    if e.unclear_words:
        worst = [w for w, _ in sorted(e.unclear_words.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
        items.append("Practise saying: " + ", ".join(worst))

    suggestion_kinds = {s["subtype"] for s in e.suggestions}
    if len(e.suggestions) >= 2 and {"weak_vocabulary", "overused_expression"} & suggestion_kinds:
        items.append("Reach for stronger, more varied words instead of repeating basic ones")

    return items[:3]


@dataclass
class ReportContent:
    scores: dict[str, int | None]
    top_errors: list[dict]
    strengths: list[str]
    improvements: list[str]


def build_report(e: Evidence, labels: dict[tuple[str, str], str]) -> ReportContent:
    scores = compute_scores(e)
    errors = top_errors(e.mistakes, labels)
    return ReportContent(
        scores=scores,
        top_errors=errors,
        strengths=build_strengths(e, scores, labels),
        improvements=build_improvements(e, scores, errors),
    )
