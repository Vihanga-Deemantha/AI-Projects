"""
ASGI middleware.

BodySizeLimitMiddleware rejects oversized request bodies with 413 BEFORE the
framework buffers them. Without it a client could stream gigabytes at an
endpoint (multipart bodies are spooled to disk ahead of any handler code), and
the in-handler size checks would only run after the damage was done.
"""
import json


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """
    Args:
        app:      the wrapped ASGI app.
        limits:   [(path_prefix, max_bytes), ...]; the first matching prefix wins.
        default:  max bytes for every other path (JSON endpoints are tiny).
    """

    def __init__(self, app, limits: list[tuple[str, int]], default: int = 1_000_000):
        self.app = app
        self.limits = limits
        self.default = default

    def _limit_for(self, path: str) -> int:
        for prefix, limit in self.limits:
            if path.startswith(prefix):
                return limit
        return self.default

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self._limit_for(scope["path"])

        # Fast path: an honest client declares its size up front.
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await self._reject(send, limit)
            return

        # Slow path: count what actually arrives (chunked bodies, lying clients).
        received = 0
        response_started = False

        async def counting_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await self._reject(send, limit)

    @staticmethod
    async def _reject(send, limit: int):
        body = json.dumps({"detail": f"Request body too large (limit {limit // 1024} KB)."}).encode()
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})
