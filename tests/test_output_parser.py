import pytest
from ling.output_parser import OutputParser, Chunk, ChunkType

def test_plain_text_flushed_on_blank_line():
    parser = OutputParser()
    chunks = []
    chunks += parser.feed_line("Hello world")
    chunks += parser.feed_line("Second line")
    chunks += parser.feed_line("")  # blank line triggers flush
    assert len(chunks) == 1
    assert chunks[0].type == ChunkType.TEXT
    assert "Hello world" in chunks[0].content
    assert "Second line" in chunks[0].content

def test_code_block_emitted_verbatim():
    parser = OutputParser()
    chunks = []
    chunks += parser.feed_line("```python")
    chunks += parser.feed_line("def foo():")
    chunks += parser.feed_line("    return 42")
    chunks += parser.feed_line("```")
    assert len(chunks) == 1
    assert chunks[0].type == ChunkType.CODE
    assert "def foo():" in chunks[0].content

def test_text_before_code_flushed_first():
    parser = OutputParser()
    chunks = []
    chunks += parser.feed_line("Here is some code:")
    chunks += parser.feed_line("```bash")
    chunks += parser.feed_line("echo hello")
    chunks += parser.feed_line("```")
    assert len(chunks) == 2
    assert chunks[0].type == ChunkType.TEXT
    assert chunks[1].type == ChunkType.CODE

def test_flush_emits_remaining_buffer():
    parser = OutputParser()
    parser.feed_line("Partial text")
    chunks = parser.flush()
    assert len(chunks) == 1
    assert chunks[0].type == ChunkType.TEXT
    assert chunks[0].content == "Partial text"

def test_ansi_codes_stripped():
    parser = OutputParser()
    parser.feed_line("\x1b[32mGreen text\x1b[0m")
    chunks = parser.flush()
    assert "\x1b" not in chunks[0].content
    assert "Green text" in chunks[0].content

def test_sequence_numbers_monotonically_increase():
    parser = OutputParser()
    parser.feed_line("First paragraph")
    c1 = parser.flush()
    parser.feed_line("Second paragraph")
    c2 = parser.flush()
    assert c2[0].seq == c1[0].seq + 1

def test_empty_input_produces_no_chunks():
    parser = OutputParser()
    chunks = parser.feed_line("")
    assert chunks == []
