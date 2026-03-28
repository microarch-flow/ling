from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum

_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# Patterns that indicate technical content not worth translating:
# file paths, shell commands, URLs, inline code fragments
_TECHNICAL_PATTERN = re.compile(
    r'(?:'
    r'(?:^|\s)(?:/[\w./\-]+){2,}'       # Unix file paths with depth >= 2
    r'|`[^`]+`'                          # inline code
    r'|https?://\S+'                     # URLs
    r'|(?:^|\s)\$\s+\S+'                # shell prompt lines
    r'|(?:^|\s)[\w./\-]+\.(?:py|ts|js|go|rs|cpp|h|yaml|toml|json|md)\b'  # filenames with extension
    r')',
    re.MULTILINE,
)

_TECHNICAL_RATIO_THRESHOLD = 0.6  # skip translation if >60% of chars are technical

def is_mostly_technical(text: str) -> bool:
    """Return True if the chunk is dominated by paths/code and shouldn't be translated."""
    if not text.strip():
        return False
    matches = _TECHNICAL_PATTERN.findall(text)
    technical_chars = sum(len(m) for m in matches)
    return technical_chars / max(len(text), 1) > _TECHNICAL_RATIO_THRESHOLD

class ChunkType(Enum):
    TEXT = "text"
    CODE = "code"

@dataclass
class Chunk:
    type: ChunkType
    content: str
    seq: int
    skip_translation: bool = False  # True for code blocks or mostly-technical text

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
                chunks.append(Chunk(ChunkType.CODE, "\n".join(self._code_lines), self._seq, skip_translation=True))
                self._seq += 1
                self._code_lines = []
                self._in_code_block = False
        elif line.startswith("```"):
            # Start of code block — flush pending text first
            if self._text_lines:
                content = "\n".join(self._text_lines)
                chunks.append(Chunk(ChunkType.TEXT, content, self._seq, skip_translation=is_mostly_technical(content)))
                self._seq += 1
                self._text_lines = []
            self._in_code_block = True
            self._code_lines = [line]
        elif line.strip() == "":
            # Blank line — flush pending text
            if self._text_lines:
                content = "\n".join(self._text_lines)
                chunks.append(Chunk(ChunkType.TEXT, content, self._seq, skip_translation=is_mostly_technical(content)))
                self._seq += 1
                self._text_lines = []
        else:
            self._text_lines.append(line)
            # Flush on sentence-ending punctuation to reduce perceived latency
            if line.rstrip().endswith((".", "!", "?", "。", "！", "？", ":", "：")):
                content = "\n".join(self._text_lines)
                chunks.append(Chunk(ChunkType.TEXT, content, self._seq, skip_translation=is_mostly_technical(content)))
                self._seq += 1
                self._text_lines = []

        return chunks

    def flush(self) -> list[Chunk]:
        """Force-emit whatever text is buffered (called on accumulate_timeout)."""
        chunks: list[Chunk] = []
        if self._text_lines:
            content = "\n".join(self._text_lines)
            chunks.append(Chunk(ChunkType.TEXT, content, self._seq, skip_translation=is_mostly_technical(content)))
            self._seq += 1
            self._text_lines = []
        # Incomplete code blocks are NOT flushed — wait for closing ```
        return chunks
