"""
Groq LLM client wrapper.
All LLM calls go through this module — never instantiate Groq() in a route directly.
"""
# pyrefly: ignore [missing-import]
from groq import Groq
from backend.config import (
    GROQ_API_KEY,
    LLM_ANALYSIS_MODEL,
    LLM_CONVERSATION_MODEL,
    LLM_REASONING_EFFORT,
)

_client: Groq | None = None


def get_client() -> Groq:
    """Returns the shared Groq client (lazy singleton)."""
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def _reasoning_kwargs() -> dict:
    """
    Extra kwargs for reasoning models (gpt-oss). Returns an empty dict when
    LLM_REASONING_EFFORT is unset, so non-reasoning models (llama-*) — which
    reject this parameter — still work without config changes.
    """
    return {"reasoning_effort": LLM_REASONING_EFFORT} if LLM_REASONING_EFFORT else {}


def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.8,
    max_tokens: int = 256,
) -> str:
    """
    Simple blocking chat completion.
    Returns the response text.

    Args:
        messages: List of {"role": ..., "content": ...} dicts (include system message).
        model: Override the default conversation model.
        temperature: Higher = more creative. Default 0.8 suits conversation.
        max_tokens: Keep short for conversational replies (256), longer for analysis.
    """
    response = get_client().chat.completions.create(
        model=model or LLM_CONVERSATION_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **_reasoning_kwargs(),
    )
    return response.choices[0].message.content


def chat_json(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    """
    Chat completion with JSON output mode.
    Use for structured analysis prompts (Phase 2+).
    Always validate the returned string with Pydantic before using it.

    Lower temperature (0.2) reduces variability in structured outputs.
    """
    response = get_client().chat.completions.create(
        model=model or LLM_ANALYSIS_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},  # Groq-supported JSON mode
        **_reasoning_kwargs(),
    )
    return response.choices[0].message.content


def ping() -> bool:
    """
    Makes a minimal API call to verify Groq connectivity.
    Returns True on success, raises on failure.
    Used by the /health endpoint.
    """
    chat(
        messages=[{"role": "user", "content": "hi"}],
        model=LLM_ANALYSIS_MODEL,  # Use fast model for health checks
        max_tokens=5,
        temperature=0,
    )
    return True


def build_messages(system_prompt: str, history: list[dict]) -> list[dict]:
    """
    Assembles the full messages list for the Groq API.

    Args:
        system_prompt: The assembled system prompt from personalities.build_system_prompt().
        history: List of {"role": "user"|"assistant", "content": str} dicts,
                 ordered oldest-first (as fetched from the DB).

    Returns:
        Complete messages list ready to pass directly to chat().

    Example:
        messages = build_messages(system_prompt, history)
        reply = chat(messages, max_tokens=150)
    """
    return [{"role": "system", "content": system_prompt}, *history]


def chat_stream(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.8,
    max_tokens: int = 300,
):
    """
    Streams tokens from Groq as they are generated.

    Yields:
        str — each token string as it arrives from the model.
              May be a word, part of a word, or punctuation.
              Do NOT assume word or sentence boundaries between yields.

    Args:
        messages:    Full messages list including system prompt (from build_messages()).
        model:       Override the default conversation model.
        temperature: Creativity level — 0.8 is good for conversational replies.
        max_tokens:  Slightly higher than chat() since sentence splitter manages
                     output length more naturally than a hard token cutoff.

    Usage:
        for token in chat_stream(messages):
            buffer += token
            sentences, buffer = split_sentences(buffer)
            for sentence in sentences:
                audio = synthesize(sentence)
                play(audio)

    Notes:
        - This is a synchronous generator — run inside asyncio.to_thread() or
          a background thread to avoid blocking the async event loop.
        - The generator will raise if the Groq API returns an error mid-stream.
    """
    stream = get_client().chat.completions.create(
        model=model or LLM_CONVERSATION_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        **_reasoning_kwargs(),
    )
    for chunk in stream:
        # A trailing usage-only chunk can carry an empty `choices` list;
        # indexing it blindly would raise IndexError and kill the stream.
        if not chunk.choices:
            continue
        # Reasoning models put internal reasoning on `delta.reasoning`, which
        # we deliberately ignore — only user-facing `content` is spoken.
        token = chunk.choices[0].delta.content
        if token:
            yield token
