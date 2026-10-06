"""
In-memory sliding-window rate limiter.

Per-process state, which is exactly right for this app's deployment shape (one
worker holding the Whisper/Piper models in RAM). If you ever run several
workers, swap the storage for Redis — the `RateLimiter` interface stays.

Two usage patterns:

  * Count every attempt (signup, forgot-password):
        enforce("signup:ip", client_ip(request), *SIGNUP_PER_IP)

  * Count only failures, so honest users are never punished (login):
        if (wait := limiter.retry_after("login:fail", key, 5, 900)): raise 429
        ... on a bad password:  limiter.record("login:fail", key)
        ... on success:         limiter.clear("login:fail", key)
"""
import math
import threading
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import HTTPException, Request, status

from backend.config import RATE_LIMITS_ENABLED

# (limit, window_seconds) policies, kept together so they're easy to audit.
LOGIN_PER_IP = (30, 15 * 60)             # every attempt
LOGIN_FAIL_PER_IP_EMAIL = (5, 15 * 60)   # failures from one IP against one email
LOGIN_FAIL_PER_EMAIL = (20, 15 * 60)     # failures against one email from anywhere
SIGNUP_PER_IP = (10, 60 * 60)
FORGOT_PER_IP = (10, 60 * 60)
FORGOT_PER_EMAIL = (3, 60 * 60)          # silently skips the email (no 429 -> no enumeration)
OTP_VERIFY_PER_EMAIL = (10, 15 * 60)
OTP_VERIFY_PER_IP = (30, 15 * 60)
EMAIL_VERIFY_PER_USER = (10, 15 * 60)
EMAIL_CODE_SEND_PER_USER = (5, 60 * 60)
AVATAR_PER_USER = (10, 60 * 60)
VOICE_TURN_PER_USER = (30, 60)
WORD_AUDIO_PER_USER = (60, 60)
ACCOUNT_DELETE_PER_USER = (5, 60 * 60)

_SWEEP_THRESHOLD = 20_000  # drop idle keys once the table gets this big


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._clock = clock

    def _recent(self, bucket: str, key: str, window: float) -> deque[float]:
        queue = self._hits[(bucket, key)]
        cutoff = self._clock() - window
        while queue and queue[0] <= cutoff:
            queue.popleft()
        return queue

    def retry_after(self, bucket: str, key: str, limit: int, window: float) -> int:
        """Seconds until another event is allowed; 0 means allowed now. Does not record."""
        if not RATE_LIMITS_ENABLED:
            return 0
        with self._lock:
            queue = self._recent(bucket, key, window)
            if len(queue) < limit:
                return 0
            return max(1, math.ceil(queue[0] + window - self._clock()))

    def record(self, bucket: str, key: str, window: float = 3600) -> None:
        if not RATE_LIMITS_ENABLED:
            return
        with self._lock:
            self._recent(bucket, key, window).append(self._clock())
            if len(self._hits) > _SWEEP_THRESHOLD:
                self._sweep(window)

    def check_and_record(self, bucket: str, key: str, limit: int, window: float) -> int:
        """Atomically: if allowed, record the event and return 0; else return retry-after seconds."""
        if not RATE_LIMITS_ENABLED:
            return 0
        with self._lock:
            queue = self._recent(bucket, key, window)
            if len(queue) >= limit:
                return max(1, math.ceil(queue[0] + window - self._clock()))
            queue.append(self._clock())
            if len(self._hits) > _SWEEP_THRESHOLD:
                self._sweep(window)
            return 0

    def clear(self, bucket: str, key: str) -> None:
        with self._lock:
            self._hits.pop((bucket, key), None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _sweep(self, window: float) -> None:
        cutoff = self._clock() - max(window, 3600)
        for k in [k for k, q in self._hits.items() if not q or q[-1] <= cutoff]:
            del self._hits[k]


limiter = RateLimiter()


def too_many(retry_after: int, detail: str = "Too many attempts. Please try again later.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After": str(retry_after)},
    )


def enforce(bucket: str, key: str, policy: tuple[int, int], detail: str | None = None) -> None:
    """Counts this event against `policy` and raises 429 if the limit is exceeded."""
    limit, window = policy
    wait = limiter.check_and_record(bucket, key, limit, window)
    if wait:
        raise too_many(wait, detail) if detail else too_many(wait)


def client_ip(request: Request) -> str:
    """
    The caller's IP. Behind a reverse proxy, run uvicorn with --proxy-headers
    (and --forwarded-allow-ips) so request.client reflects X-Forwarded-For.
    """
    return request.client.host if request.client else "unknown"
