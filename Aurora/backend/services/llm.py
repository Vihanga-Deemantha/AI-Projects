"""
Groq LLM client wrapper.
All LLM calls go through this module — never instantiate Groq() in a route directly.
"""
from groq import Groq
from backend.config import GROQ_API_KEY, LLM_CONVERSATION_MODEL, LLM_ANALYSIS_MODEL

_client: Groq | None = None


def get_client() -> Groq:
    """Returns the shared Groq client (lazy singleton)."""
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


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
