"""
Fire-and-forget background work that must outlive the request that started it.

FastAPI's BackgroundTasks only start AFTER the response has finished — for a
streamed reply that means the grammar analysis (which takes a couple of
seconds) would not even begin until the spoken answer was over, so feedback
always arrived a turn late. `spawn()` starts the work immediately, concurrently
with the rest of the stream, in a worker thread.

Tasks are held in a set so the event loop can't garbage-collect them mid-flight
(asyncio only keeps weak references to running tasks).
"""
import asyncio
import logging
from typing import Any, Callable

logger = logging.getLogger("aura.background")

_tasks: set[asyncio.Task] = set()


def spawn(func: Callable[..., Any], *args: Any, **kwargs: Any) -> asyncio.Task:
    """Runs a blocking `func` in a worker thread without awaiting it. Must be called from async code."""
    task = asyncio.create_task(asyncio.to_thread(func, *args, **kwargs))
    _tasks.add(task)
    task.add_done_callback(_finished)
    return task


def _finished(task: asyncio.Task) -> None:
    _tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("Background task failed", exc_info=exc)
