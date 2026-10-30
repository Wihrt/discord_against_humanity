"""asyncio implementation of the :class:`Scheduler` port."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class AsyncioScheduler:
    """One sleeping task per key; scheduling again replaces the pending one."""

    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task[None]] = {}

    def schedule(self, key: int, when: datetime, action: Callable[[], Awaitable[None]]) -> None:
        self.cancel(key)
        delay = max((when - datetime.now(UTC)).total_seconds(), 0.0)
        self._tasks[key] = asyncio.create_task(self._run(key, delay, action))

    def cancel(self, key: int) -> None:
        task = self._tasks.pop(key, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    def pending(self) -> set[int]:
        return set(self._tasks)

    async def close(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, key: int, delay: float, action: Callable[[], Awaitable[None]]) -> None:
        await asyncio.sleep(delay)
        # Forget this task before acting, so that the action may schedule the
        # next deadline for the same key without cancelling itself.
        if self._tasks.get(key) is asyncio.current_task():
            del self._tasks[key]
        try:
            await action()
        except Exception:
            logger.exception("Scheduled action for %s failed", key)
