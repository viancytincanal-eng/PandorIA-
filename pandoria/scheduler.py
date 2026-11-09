"""Bounded asynchronous task execution."""
import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar
T = TypeVar("T")

class BoundedScheduler:
    def __init__(self, max_concurrency: int = 8) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self._semaphore = asyncio.Semaphore(max_concurrency)
    async def run(self, operation: Callable[[], Awaitable[T]], timeout: float) -> tuple[T, float]:
        started = time.perf_counter()
        async with self._semaphore:
            result = await asyncio.wait_for(operation(), timeout=timeout)
        return result, (time.perf_counter() - started) * 1000
