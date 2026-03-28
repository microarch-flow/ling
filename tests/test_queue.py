import asyncio
import pytest
from ling.queue import TranslationQueue, QueueItem

async def make_translator(delay: float = 0.0):
    async def translate(text: str) -> str:
        await asyncio.sleep(delay)
        return f"[{text}]"
    return translate

async def test_text_chunk_gets_translated():
    results = []
    translate = await make_translator()
    queue = TranslationQueue(translate, lambda seq, text, is_code: results.append((seq, text, is_code)))
    await queue.enqueue(QueueItem(seq=0, text="hello", is_code=False))
    await asyncio.sleep(0.05)
    assert results == [(0, "[hello]", False)]

async def test_code_chunk_bypasses_translation():
    results = []
    translate = await make_translator()
    queue = TranslationQueue(translate, lambda seq, text, is_code: results.append((seq, text, is_code)))
    await queue.enqueue(QueueItem(seq=0, text="```\ncode\n```", is_code=True))
    assert results == [(0, "```\ncode\n```", True)]

async def test_output_order_preserved_despite_variable_latency():
    results = []

    call_count = 0
    async def slow_then_fast(text: str) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await asyncio.sleep(0.1)  # first chunk is slow
        else:
            await asyncio.sleep(0.0)  # second chunk is fast
        return f"[{text}]"

    queue = TranslationQueue(
        slow_then_fast,
        lambda seq, text, is_code: results.append((seq, text))
    )
    await queue.enqueue(QueueItem(seq=0, text="first", is_code=False))
    await queue.enqueue(QueueItem(seq=1, text="second", is_code=False))
    await asyncio.sleep(0.2)
    # Despite seq=1 finishing faster, seq=0 must appear first
    assert results[0] == (0, "[first]")
    assert results[1] == (1, "[second]")

async def test_mixed_code_and_text_ordering():
    results = []
    translate = await make_translator(delay=0.01)
    queue = TranslationQueue(translate, lambda seq, text, is_code: results.append(seq))
    await queue.enqueue(QueueItem(seq=0, text="text A", is_code=False))
    await queue.enqueue(QueueItem(seq=1, text="```code```", is_code=True))
    await queue.enqueue(QueueItem(seq=2, text="text B", is_code=False))
    await asyncio.sleep(0.1)
    assert results == [0, 1, 2]
