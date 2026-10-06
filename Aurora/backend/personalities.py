"""
Personality, style, and scenario system for AURA.

What shapes a session:
- Companion (a key of VOICES) = who you talk to: name, face, gender, and a HOME voice
  (a Piper .onnx model).
- Style = the English variety. It changes the coach's WORDS (an LLM prompt modifier) and the
  ACCENT you hear: a companion speaks with a voice of the style's accent (ACCENT_VOICES), or with
  their own voice for Standard English or when the style matches their home accent.
- Scenario = the conversational context/role the AI takes on.

Scenario is independent of the other two. Not every companion has a voice for every accent
(voice_for returns None, e.g. there is no Australian-accent voice for the female companions), and
the UI only offers combinations that work.
"""

# ── Voices (TTS models) ───────────────────────────────────────────────────────
VOICES = {
    "eida": {
        "file": "voices/en_US-kristin-medium.onnx",
        "label": "Eida",
        "desc": "Calm, unhurried",
        "gender": "female",
        "accent": "american",
    },
    "maya": {
        "file": "voices/en_US-hfc_female-medium.onnx",
        "label": "Maya",
        "desc": "Upbeat, energetic",
        "gender": "female",
        "accent": "american",
    },
    "amy": {
        "file": "voices/en_US-amy-medium.onnx",
        "label": "Amy",
        "desc": "Friendly, American",
        "gender": "female",
        "accent": "american",
    },
    "ryan": {
        "file": "voices/en_US-ryan-high.onnx",
        "label": "Ryan",
        "desc": "Warm, American",
        "gender": "male",
        "accent": "american",
    },
    "alan": {
        "file": "voices/en_GB-alan-medium.onnx",
        "label": "Alan",
        "desc": "Measured, British",
        "gender": "male",
        "accent": "british",
    },
    "lessac": {
        "file": "voices/en_US-norman-medium.onnx",
        "label": "Lessac",
        "desc": "Deep, deliberate",
        "gender": "male",
        "accent": "american",
    },
}

DEFAULT_VOICE = "amy"

# The accent of each companion's own voice is the "accent" key above. The names people see:
ACCENT_LABELS = {
    "american": "American",
    "british": "British",
    "australian": "Australian",
    "irish": "Irish",
    "scottish": "Scottish",
    "canadian": "Canadian",
}

# ── Speaking Styles (LLM prompt modifiers) ────────────────────────────────────
# Real English varieties a learner is likely to meet at work, at university and
# while travelling. A style changes the coach's VOCABULARY, IDIOM and PHRASING (the
# prompt) AND the ACCENT of the voice (see ACCENT_VOICES below): the words and the sound
# always agree. Prompts ask for light, natural usage: no caricature, no phonetic dialect
# spelling, nothing that mocks or stereotypes a community. "standard" has no accent of its
# own: the companion speaks with their own voice.
STYLES = {
    "standard": {
        "label": "Standard English",
        "desc": "Clear and neutral — a safe default",
        "accent": None,
        "prompt": "Speak in clear, neutral Standard English.",
    },
    "american": {
        "label": "American English",
        "accent": "american",
        "desc": "apartment, elevator, sidewalk, \"I've gotten\"",
        "prompt": (
            "Use natural American English vocabulary and phrasing where it fits, "
            "for example 'apartment', 'elevator', 'sidewalk', 'I've gotten', 'sounds good'. "
            "Keep it clear and easy for a learner to follow."
        ),
    },
    "british": {
        "label": "British English",
        "accent": "british",
        "desc": "flat, lift, queue, \"not bad\", \"cheers\"",
        "prompt": (
            "Use natural British English vocabulary and phrasing where it fits, "
            "for example 'flat', 'lift', 'queue', 'holiday', 'cheers', 'lovely', "
            "and the understated 'not bad' or 'quite good'. Keep it clear and easy for a learner to follow."
        ),
    },
    "australian": {
        "label": "Australian English",
        "accent": "australian",
        "desc": "arvo, reckon, \"no worries\", \"heaps\"",
        "prompt": (
            "Use light, natural Australian English phrasing where it fits, "
            "for example 'no worries', 'reckon', 'arvo', 'heaps good', 'good on you'. "
            "Keep a relaxed, friendly tone and stay easy for a learner to follow."
        ),
    },
    "irish": {
        "label": "Irish English",
        "accent": "irish",
        "desc": "grand, \"sure look\", \"fair play\"",
        "prompt": (
            "Use light, natural Irish English phrasing where it fits, "
            "for example 'grand', 'sure look', 'fair play', 'how are you keeping', 'I will, yeah'. "
            "Keep a warm, conversational tone and stay easy for a learner to follow."
        ),
    },
    "scottish": {
        "label": "Scottish English",
        "accent": "scottish",
        "desc": "wee, aye, \"how's it going\"",
        "prompt": (
            "Use light, natural Scottish English phrasing where it fits, "
            "for example 'wee', 'aye', 'braw', 'how's it going'. "
            "Keep standard grammar and spelling and stay easy for a learner to follow."
        ),
    },
    "canadian": {
        "label": "Canadian English",
        "accent": "canadian",
        "desc": "washroom, toque, \"eh\", \"double-double\"",
        "prompt": (
            "Use light, natural Canadian English vocabulary and phrasing where it fits, "
            "for example 'washroom', 'toque', 'loonie', 'eh' used sparingly, 'give'r'. "
            "Keep it friendly and easy for a learner to follow."
        ),
    },
}

# Appended to every non-standard style so the guardrails live in one place.
STYLE_GUARDRAILS = (
    "Keep spelling standard and never write phonetic dialect. Never exaggerate, "
    "mock or stereotype the variety or the people who speak it. Your reply must "
    "stay clear and easy for an English learner to understand."
)

DEFAULT_STYLE = "standard"

# ── Accent voices ─────────────────────────────────────────────────────────────
# When the chosen style has an accent that differs from a companion's own, the companion speaks with
# one of these voices: the same companion (name, face), a voice of that accent, matched to their gender.
# Where no voice exists the entry is simply absent and that pair is not offered: nothing is faked.
#
# The voices are real speakers of those accents, from two University of Edinburgh (CSTR) datasets
# released under CC BY 4.0 (credit them wherever the app credits its voices):
#   * the VCTK corpus, 109 speakers, accent and region recorded for each speaker, served by the multi-
#     speaker Piper model below (one ~77 MB model holds all of them);
#   * Alba, a Scottish voice of her own.
# The comments give each speaker's gender and region from VCTK's own speaker table. Companions get
# different speakers where there are enough (Eida, Maya and Amy never share a voice for the same
# accent); only two Australian speakers exist, both male, so only Ryan and Alan can speak Australian
# English.
VCTK_MODEL = "voices/en_GB-vctk-medium.onnx"
ALBA_MODEL = "voices/en_GB-alba-medium.onnx"


def _vctk(speaker: str, gender: str, region: str) -> dict:
    return {"file": VCTK_MODEL, "speaker": speaker, "gender": gender, "region": region}


_ALBA = {"file": ALBA_MODEL, "speaker": None, "gender": "female", "region": "Edinburgh"}

ACCENT_VOICES = {
    "american": {   # the others already speak American
        "alan": _vctk("p311", "male", "Iowa"),
    },
    "british": {    # Alan already speaks British
        "eida": _vctk("p268", "female", "Southern England"),
        "maya": _vctk("p229", "female", "Southern England"),
        "amy": _vctk("p225", "female", "Southern England"),
        "ryan": _vctk("p254", "male", "Surrey"),
        "lessac": _vctk("p226", "male", "Surrey"),
    },
    "scottish": {
        "eida": _ALBA,
        "maya": _vctk("p234", "female", "West Dumfries"),
        "amy": _vctk("p262", "female", "Edinburgh"),
        "ryan": _vctk("p281", "male", "Edinburgh"),
        "alan": _vctk("p272", "male", "Edinburgh"),
        "lessac": _vctk("p246", "male", "Selkirk"),
    },
    "irish": {
        "eida": _vctk("p283", "female", "Cork"),
        "maya": _vctk("p295", "female", "Dublin"),
        "amy": _vctk("p340", "female", "Dublin"),
        "ryan": _vctk("p298", "male", "Tipperary"),
        "alan": _vctk("p364", "male", "Donegal"),
        "lessac": _vctk("p245", "male", "Dublin"),
    },
    "canadian": {
        "eida": _vctk("p343", "female", "Alberta"),
        "maya": _vctk("p312", "female", "Hamilton"),
        "amy": _vctk("p303", "female", "Toronto"),
        "ryan": _vctk("p302", "male", "Montreal"),
        "alan": _vctk("p363", "male", "Toronto"),
        "lessac": _vctk("p316", "male", "Alberta"),
    },
    "australian": {   # only two Australian speakers exist in the data, both male
        "ryan": _vctk("p326", "male", "Sydney"),
        "alan": _vctk("p374", "male", "Australia"),
    },
}


def accent_of(style: str) -> str | None:
    """The accent a speaking style asks for (None for Standard English or an unknown style)."""
    return STYLES.get(style, {}).get("accent")


def voice_for(companion: str, style: str) -> dict | None:
    """
    The voice `companion` speaks with under `style`: {"file", "speaker", "gender", "region"}, or None when
    there isn't one. Standard English, or a style whose accent is the companion's own, uses their own voice.
    """
    own = VOICES[companion]
    accent = accent_of(style)
    if accent is None or accent == own["accent"]:
        return {"file": own["file"], "speaker": None, "gender": own["gender"], "region": None}
    spec = ACCENT_VOICES.get(accent, {}).get(companion)
    return dict(spec) if spec else None


def model_files() -> list[str]:
    """Every voice model file the app can use (companions' own first), without repeats."""
    files = [v["file"] for v in VOICES.values()]
    for by_companion in ACCENT_VOICES.values():
        files += [spec["file"] for spec in by_companion.values()]
    return list(dict.fromkeys(files))

# ── Conversation Scenarios ────────────────────────────────────────────────────
SCENARIOS = {
    "casual": {
        "label": "Casual Conversation",
        "prompt": (
            "Have a warm, natural casual conversation. Ask about the user's day, "
            "hobbies, opinions on everyday topics. Keep turns short and relaxed."
        ),
    },
    "interview": {
        "label": "Job Interview Practice",
        "prompt": (
            "You are a friendly but professional interviewer. Ask common job interview "
            "questions: strengths, weaknesses, past experience, motivation. "
            "React naturally to answers. Gradually increase question complexity."
        ),
    },
    "travel": {
        "label": "Travel English",
        "prompt": (
            "Simulate travel situations: at the airport, checking into a hotel, "
            "ordering food, asking for directions, booking activities. "
            "Play the role of staff or locals the user encounters."
        ),
    },
    "debate": {
        "label": "Debate",
        "prompt": (
            "Pick a side on a topic and debate respectfully with the user. "
            "Challenge their arguments, ask for evidence, introduce counter-points. "
            "Topics: technology, environment, education, lifestyle choices."
        ),
    },
    "seminar": {
        "label": "University Seminar",
        "prompt": (
            "Simulate an academic context: seminar discussion, study group, "
            "office hours with a professor. Use academic vocabulary. "
            "Ask the user to explain concepts, give opinions on readings, present ideas."
        ),
    },
    "cafe": {
        "label": "Café / Ordering",
        "prompt": (
            "You are a friendly barista or waiter at a busy café. Take the user's order, "
            "suggest options, mention when something is unavailable, and ask clarifying "
            "questions (size, milk, for here or to go). Keep it fast and natural, the way "
            "real service conversations go."
        ),
    },
    "phone": {
        "label": "Phone Call",
        "prompt": (
            "Simulate a phone call with no visual cues: a booking line, customer service "
            "or a colleague. Ask the user to spell names, repeat numbers and confirm details. "
            "Occasionally ask them to repeat or clarify, as on a slightly bad line."
        ),
    },
}

DEFAULT_SCENARIO = "casual"

# ── Difficulty tiers (Phase 10) ───────────────────────────────────────────────
# How demanding the coach's questions are. The tier is chosen automatically from
# recent session scores (services/difficulty.py) unless the user pins one on
# their profile. `prompt` is appended to the system prompt; `example` is shown
# in the UI so a level means something concrete.
DIFFICULTY_LEVELS = {
    1: {
        "label": "Beginner",
        "prompt": (
            "Use very simple, everyday questions with basic vocabulary and short sentences. "
            "Speak slowly in your word choice, one idea at a time."
        ),
        "example": "What did you do today?",
    },
    2: {
        "label": "Elementary",
        "prompt": (
            "Use clear questions with slightly more detail. Keep vocabulary common and "
            "sentences short, and invite one extra detail in the answer."
        ),
        "example": "What was the most interesting part of your day?",
    },
    3: {
        "label": "Intermediate",
        "prompt": (
            "Ask questions that need an explanation or an opinion with a reason. "
            "Use natural everyday vocabulary and some common idioms."
        ),
        "example": "Do you prefer working alone or in a team? Why?",
    },
    4: {
        "label": "Upper-Intermediate",
        "prompt": (
            "Ask nuanced questions that need structured reasoning and comparison. "
            "Use richer vocabulary, phrasal verbs and idiomatic expressions naturally."
        ),
        "example": "What do you think are the most important skills for success today?",
    },
    5: {
        "label": "Advanced",
        "prompt": (
            "Ask complex questions about abstract topics, hypotheticals and trade-offs, "
            "and challenge the user's reasoning. Use sophisticated vocabulary and idiom."
        ),
        "example": "Do you think AI will fundamentally change how humans learn languages? Defend your view.",
    },
}

DEFAULT_DIFFICULTY = 2

# ── Coaching Instructions (always included) ───────────────────────────────────
COACHING_INSTRUCTIONS = """
You are AURA, an AI English speaking coach. Your role is to have natural,
encouraging conversations while helping the user practice English.

Guidelines:
- Keep your replies concise: 2-3 sentences maximum per turn.
- Be warm, supportive, and encouraging — not robotic or clinical.
- Ask a follow-up question to keep the conversation flowing naturally.
- If the user makes a very obvious grammatical error, you may very gently model
  the correct form in your reply (without saying "you made an error"),
  but never more than once per session. Detailed corrections come separately.
- Never break character to explain what you are doing.
- CRITICAL: Always end your reply with a sentence-ending punctuation mark (. ! ?).
  Never stop mid-sentence. Complete every sentence before ending your reply.
"""


def build_system_prompt(
    scenario: str = DEFAULT_SCENARIO,
    style: str = DEFAULT_STYLE,
    difficulty: int | None = None,
    focus: str | None = None,
) -> str:
    """
    Assembles the full system prompt from scenario + style + difficulty + focus +
    coaching instructions.

    Args:
        scenario:   One of the keys in SCENARIOS dict.
        style:      One of the keys in STYLES dict. Non-standard styles also get
                    STYLE_GUARDRAILS (no caricature, no phonetic dialect, no mockery).
        difficulty: A key of DIFFICULTY_LEVELS (1-5), or None for no instruction.
        focus:      A steering instruction (taxonomy "focus" text) naming what today's
                    conversation should give the learner practice at, or None. It is
                    used silently: the coach never announces it or quizzes.

    Returns:
        A single system prompt string to pass as the 'system' message to the LLM.
    """
    scenario_data = SCENARIOS.get(scenario, SCENARIOS[DEFAULT_SCENARIO])
    style_data = STYLES.get(style, STYLES[DEFAULT_STYLE])

    parts = [
        COACHING_INSTRUCTIONS.strip(),
        f"SCENARIO: {scenario_data['prompt']}",
        f"SPEAKING STYLE: {style_data['prompt']}"
        + (f" {STYLE_GUARDRAILS}" if style in STYLES and style != DEFAULT_STYLE else ""),
    ]
    if difficulty in DIFFICULTY_LEVELS:
        parts.append(f"DIFFICULTY ({DIFFICULTY_LEVELS[difficulty]['label']}): {DIFFICULTY_LEVELS[difficulty]['prompt']}")
    if focus:
        parts.append(
            "HIDDEN PRACTICE FOCUS: through your own questions and the topics you raise, steer the "
            f"conversation toward {focus}. The learner gets practice at this without noticing. "
            "NEVER mention this focus, name a grammar point, quiz them, or lecture."
        )
    return "\n\n".join(parts)
