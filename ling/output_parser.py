from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum

_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

class ChunkType(Enum):
    TEXT = "text"
    CODE = "code"

@dataclass
class Chunk:
    type: ChunkType
    content: str
    seq: int

def strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)

class OutputParser:
    """
    Line-oriented parser for PTY output.
    Detects markdown code blocks (``` delimited) and emits them verbatim.
    Accumulates plain text lines and flushes on blank lines or explicit flush().
    """

    def __init__(self):
        self._in_code_block = False
        self._code_lines: list[str] = []
        self._text_lines: list[str] = []
        self._seq = 0

    def feed_line(self, raw_line: str) -> list[Chunk]:
        """Process one decoded line (no trailing newline). Returns completed chunks."""
        line = strip_ansi(raw_line)
        chunks: list[Chunk] = []

        if self._in_code_block:
            self._code_lines.append(line)
            if line.startswith("```") and len(self._code_lines) > 1:
                # End of code block
                chunks.append(Chunk(ChunkType.CODE, "\n".join(self._code_lines), self._seq))
                self._seq += 1
                self._code_lines = []
                self._in_code_block = False
        elif line.startswith("```"):
            # Start of code block — flush pending text first
            if self._text_lines:
                chunks.append(Chunk(ChunkType.TEXT, "\n".join(self._text_lines), self._seq))
                self._seq += 1
                self._text_lines = []
            self._in_code_block = True
            self._code_lines = [line]
        elif line.strip() == "":
            # Blank line — flush pending text
            if self._text_lines:
                chunks.append(Chunk(ChunkType.TEXT, "\n".join(self._text_lines), self._seq))
                self._seq += 1
                self._text_lines = []
        else:
            self._text_lines.append(line)

        return chunks

    def flush(self) -> list[Chunk]:
        """Force-emit whatever text is buffered (called on accumulate_timeout)."""
        chunks: list[Chunk] = []
        if self._text_lines:
            chunks.append(Chunk(ChunkType.TEXT, "\n".join(self._text_lines), self._seq))
            self._seq += 1
            self._text_lines = []
        # Incomplete code blocks are NOT flushed — wait for closing ```
        return chunks
