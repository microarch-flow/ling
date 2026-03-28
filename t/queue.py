from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Callable, Awaitable

@dataclass
class QueueItem:
    seq: int
    text: str
    is_code: bool

class TranslationQueue:
    """
    Ordered async translation queue.
    Items are translated concurrently but delivered to on_result in seq order.
    Code items skip translation and are delivered immediately (but still in order).
    """

    def __init__(
        self,
        translate_fn: Callable[[str], Awaitable[str]],
        on_result: Callable[[int, str, bool], None],
    ):
        self._translate = translate_fn
        self._on_result = on_result
        self._results: dict[int, tuple[str, bool]] = {}
        self._next_seq = 0
        self._lock = asyncio.Lock()

    async def enqueue(self, item: QueueItem) -> None:
        if item.is_code:
            async with self._lock:
                self._results[item.seq] = (item.text, True)
                self._flush_ready()
        else:
            asyncio.create_task(self._translate_item(item))

    async def _translate_item(self, item: QueueItem) -> None:
        translated = await self._translate(item.text)
        async with self._lock:
            self._results[item.seq] = (translated, False)
            self._flush_ready()

    def _flush_ready(self) -> None:
        """Must be called under self._lock."""
        while self._next_seq in self._results:
            text, is_code = self._results.pop(self._next_seq)
            self._on_result(self._next_seq, text, is_code)
            self._next_seq += 1
