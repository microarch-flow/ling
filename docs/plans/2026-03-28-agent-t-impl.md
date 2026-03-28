# Agent T Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Agent T — a CLI translation proxy that wraps Claude Code / Codex CLI, translating Chinese↔English in real-time with code blocks passed through verbatim.

**Architecture:** A prompt_toolkit TUI captures Chinese user input, translates it to English via a configurable third-party LLM API, and sends it to CC through a PTY. CC's streaming output is parsed into text/code chunks; text chunks are queued for async ordered translation back to Chinese while code blocks display verbatim.

**Tech Stack:** Python 3.11+, `prompt_toolkit`, `ptyprocess`, `asyncio`, `httpx`, `pyyaml`, `pytest`, `pytest-asyncio`

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `t/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "agent-t"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "prompt-toolkit>=3.0",
    "ptyprocess>=0.7",
    "httpx>=0.27",
    "pyyaml>=6.0",
]

[project.scripts]
t = "t.main:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
]
```

- [ ] **Step 2: Create package stubs**

```python
# t/__init__.py
# (empty)
```

```python
# tests/__init__.py
# (empty)
```

- [ ] **Step 3: Install dependencies**

Run: `pip install -e ".[dev]"`
Expected: Successfully installed agent-t and all dependencies

- [ ] **Step 4: Commit**

```bash
git init
git add pyproject.toml t/__init__.py tests/__init__.py
git commit -m "chore: project scaffold"
```

---

## Task 2: Config Module

**Files:**
- Create: `t/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
import pytest
import tempfile
from pathlib import Path
from t.config import load_config, Config, TranslatorConfig, CLIConfig

VALID_YAML = """
translator:
  provider: openai
  api_key: sk-test
  model: gpt-4o
  base_url: https://api.example.com
  accumulate_timeout: 2.0
  request_timeout: 30
  fallback_on_timeout: true
cli:
  command: claude
  args: []
"""

MINIMAL_YAML = """
translator:
  provider: anthropic
  api_key: sk-ant-test
  model: claude-opus-4-6
cli:
  command: claude
"""

def write_config(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.flush()
    return Path(f.name)

def test_load_full_config():
    path = write_config(VALID_YAML)
    config = load_config(path)
    assert config.translator.provider == "openai"
    assert config.translator.api_key == "sk-test"
    assert config.translator.model == "gpt-4o"
    assert config.translator.base_url == "https://api.example.com"
    assert config.translator.accumulate_timeout == 2.0
    assert config.translator.request_timeout == 30
    assert config.translator.fallback_on_timeout is True
    assert config.cli.command == "claude"
    assert config.cli.args == []

def test_load_minimal_config_uses_defaults():
    path = write_config(MINIMAL_YAML)
    config = load_config(path)
    assert config.translator.provider == "anthropic"
    assert config.translator.base_url is None
    assert config.translator.accumulate_timeout == 2.0
    assert config.translator.request_timeout == 30
    assert config.translator.fallback_on_timeout is True
    assert config.cli.args == []

def test_invalid_provider_raises():
    yaml = VALID_YAML.replace("provider: openai", "provider: unknown")
    path = write_config(yaml)
    with pytest.raises(ValueError, match="provider"):
        load_config(path)

def test_missing_api_key_raises():
    yaml = "\n".join(l for l in VALID_YAML.splitlines() if "api_key" not in l)
    path = write_config(yaml)
    with pytest.raises(ValueError, match="api_key"):
        load_config(path)
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 't.config'`

- [ ] **Step 3: Implement config.py**

```python
# t/config.py
from dataclasses import dataclass, field
from pathlib import Path
import yaml

VALID_PROVIDERS = {"openai", "anthropic"}

@dataclass
class TranslatorConfig:
    provider: str
    api_key: str
    model: str
    base_url: str | None = None
    accumulate_timeout: float = 2.0
    request_timeout: int = 30
    fallback_on_timeout: bool = True

@dataclass
class CLIConfig:
    command: str = "claude"
    args: list[str] = field(default_factory=list)

@dataclass
class Config:
    translator: TranslatorConfig
    cli: CLIConfig

def load_config(path: Path) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)

    t = raw.get("translator", {})
    if "api_key" not in t:
        raise ValueError("translator.api_key is required")
    provider = t.get("provider", "openai")
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"translator.provider must be one of {VALID_PROVIDERS}, got '{provider}'")

    translator = TranslatorConfig(
        provider=provider,
        api_key=t["api_key"],
        model=t["model"],
        base_url=t.get("base_url"),
        accumulate_timeout=float(t.get("accumulate_timeout", 2.0)),
        request_timeout=int(t.get("request_timeout", 30)),
        fallback_on_timeout=bool(t.get("fallback_on_timeout", True)),
    )

    c = raw.get("cli", {})
    cli = CLIConfig(
        command=c.get("command", "claude"),
        args=c.get("args") or [],
    )

    return Config(translator=translator, cli=cli)

def default_config_path() -> Path:
    return Path.home() / ".t" / "config.yaml"
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add t/config.py tests/test_config.py
git commit -m "feat: config loading with validation"
```

---

## Task 3: Output Parser

**Files:**
- Create: `t/output_parser.py`
- Create: `tests/test_output_parser.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_output_parser.py
import pytest
from t.output_parser import OutputParser, Chunk, ChunkType

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
    chunks = parser.feed_line("\x1b[32mGreen text\x1b[0m")
    parser.feed_line("")
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
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_output_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 't.output_parser'`

- [ ] **Step 3: Implement output_parser.py**

```python
# t/output_parser.py
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
        """Force-emit whatever is buffered (called on accumulate_timeout)."""
        chunks: list[Chunk] = []
        if self._text_lines:
            chunks.append(Chunk(ChunkType.TEXT, "\n".join(self._text_lines), self._seq))
            self._seq += 1
            self._text_lines = []
        # Note: incomplete code blocks are NOT flushed — wait for closing ```
        return chunks
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `pytest tests/test_output_parser.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add t/output_parser.py tests/test_output_parser.py
git commit -m "feat: output parser with code block detection and ANSI stripping"
```

---

## Task 4: Translator Client

**Files:**
- Create: `t/translator.py`
- Create: `tests/test_translator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_translator.py
import pytest
import httpx
import respx
from t.config import TranslatorConfig
from t.translator import TranslatorClient

OPENAI_CONFIG = TranslatorConfig(
    provider="openai",
    api_key="sk-test",
    model="gpt-4o",
    base_url="https://api.openai.com",
    request_timeout=10,
    fallback_on_timeout=True,
)

ANTHROPIC_CONFIG = TranslatorConfig(
    provider="anthropic",
    api_key="sk-ant-test",
    model="claude-opus-4-6",
    base_url="https://api.anthropic.com",
    request_timeout=10,
    fallback_on_timeout=True,
)

OPENAI_RESPONSE = {
    "choices": [{"message": {"content": "你好世界"}}]
}

ANTHROPIC_RESPONSE = {
    "content": [{"type": "text", "text": "你好世界"}]
}

@respx.mock
async def test_translate_openai_format():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=OPENAI_RESPONSE)
    )
    client = TranslatorClient(OPENAI_CONFIG)
    result = await client.translate("Hello world", target_lang="zh")
    assert result == "你好世界"
    await client.close()

@respx.mock
async def test_translate_anthropic_format():
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json=ANTHROPIC_RESPONSE)
    )
    client = TranslatorClient(ANTHROPIC_CONFIG)
    result = await client.translate("Hello world", target_lang="zh")
    assert result == "你好世界"
    await client.close()

@respx.mock
async def test_openai_sends_correct_headers():
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=OPENAI_RESPONSE)
    )
    client = TranslatorClient(OPENAI_CONFIG)
    await client.translate("test", target_lang="zh")
    assert route.called
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer sk-test"
    await client.close()

@respx.mock
async def test_anthropic_sends_correct_headers():
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json=ANTHROPIC_RESPONSE)
    )
    client = TranslatorClient(ANTHROPIC_CONFIG)
    await client.translate("test", target_lang="zh")
    assert route.called
    request = route.calls[0].request
    assert request.headers["x-api-key"] == "sk-ant-test"
    await client.close()

@respx.mock
async def test_fallback_on_timeout_returns_original():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    client = TranslatorClient(OPENAI_CONFIG)
    result = await client.translate("Hello world", target_lang="zh")
    assert result == "Hello world"  # fallback to original
    await client.close()

@respx.mock
async def test_custom_base_url():
    config = TranslatorConfig(
        provider="openai",
        api_key="sk-test",
        model="gpt-4o",
        base_url="https://custom.proxy.com",
        request_timeout=10,
    )
    route = respx.post("https://custom.proxy.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=OPENAI_RESPONSE)
    )
    client = TranslatorClient(config)
    await client.translate("test", target_lang="zh")
    assert route.called
    await client.close()
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_translator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 't.translator'`

- [ ] **Step 3: Implement translator.py**

```python
# t/translator.py
import httpx
from .config import TranslatorConfig

_ZH_PROMPT = (
    "You are a professional technical translator. "
    "Translate the following English text to Chinese. "
    "Preserve all technical terms, command names, and formatting exactly. "
    "Output only the translation, nothing else."
)
_EN_PROMPT = (
    "You are a professional technical translator. "
    "Translate the following Chinese text to English. "
    "Preserve all technical terms, command names, and formatting exactly. "
    "Output only the translation, nothing else."
)

class TranslatorClient:
    def __init__(self, config: TranslatorConfig):
        self._config = config
        self._client = httpx.AsyncClient(timeout=config.request_timeout)

    async def translate(self, text: str, target_lang: str = "zh") -> str:
        """
        Translate text. target_lang: 'zh' (→Chinese) or 'en' (→English).
        Returns original text on timeout if fallback_on_timeout is True.
        """
        try:
            if self._config.provider == "openai":
                return await self._call_openai(text, target_lang)
            else:
                return await self._call_anthropic(text, target_lang)
        except httpx.TimeoutException:
            if self._config.fallback_on_timeout:
                return text
            raise

    async def _call_openai(self, text: str, target_lang: str) -> str:
        base = (self._config.base_url or "https://api.openai.com").rstrip("/")
        system = _ZH_PROMPT if target_lang == "zh" else _EN_PROMPT
        resp = await self._client.post(
            f"{base}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._config.api_key}"},
            json={
                "model": self._config.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def _call_anthropic(self, text: str, target_lang: str) -> str:
        base = (self._config.base_url or "https://api.anthropic.com").rstrip("/")
        system = _ZH_PROMPT if target_lang == "zh" else _EN_PROMPT
        resp = await self._client.post(
            f"{base}/v1/messages",
            headers={
                "x-api-key": self._config.api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": self._config.model,
                "max_tokens": 4096,
                "system": system,
                "messages": [{"role": "user", "content": text}],
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

    async def close(self):
        await self._client.aclose()
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `pytest tests/test_translator.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add t/translator.py tests/test_translator.py
git commit -m "feat: translation client supporting OpenAI and Anthropic API formats"
```

---

## Task 5: Translation Queue

**Files:**
- Create: `t/queue.py`
- Create: `tests/test_queue.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_queue.py
import asyncio
import pytest
from t.queue import TranslationQueue, QueueItem

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
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_queue.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 't.queue'`

- [ ] **Step 3: Implement queue.py**

```python
# t/queue.py
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
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `pytest tests/test_queue.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add t/queue.py tests/test_queue.py
git commit -m "feat: ordered async translation queue with code bypass"
```

---

## Task 6: PTY Manager

**Files:**
- Create: `t/pty_manager.py`

- [ ] **Step 1: Implement pty_manager.py**

PTY manager is integration-level — tested via manual smoke test in Task 8. Unit testing PTY processes is brittle; we verify behavior end-to-end.

```python
# t/pty_manager.py
import asyncio
import os
import signal
from ptyprocess import PtyProcess

class PTYManager:
    """
    Manages the lifecycle of a CLI process (e.g. claude, codex) attached to a PTY.
    Provides async read and synchronous write.
    Signal forwarding lets T intercept Ctrl+C and forward it to the child.
    """

    def __init__(self, command: str, args: list[str], cols: int = 220, rows: int = 50):
        self._command = command
        self._args = args
        self._cols = cols
        self._rows = rows
        self._process: PtyProcess | None = None

    def start(self) -> None:
        cmd = [self._command] + self._args
        self._process = PtyProcess.spawn(cmd, dimensions=(self._rows, self._cols))

    async def read(self, size: int = 4096) -> bytes:
        """
        Async read from PTY. Returns b"" on EOF (process exited).
        Runs blocking read in thread executor to avoid blocking the event loop.
        """
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, self._process.read, size)
        except EOFError:
            return b""

    def write(self, data: bytes) -> None:
        """Write bytes to PTY stdin (send to child process)."""
        if self._process and self._process.isalive():
            self._process.write(data)

    def write_line(self, text: str) -> None:
        """Write a line of text followed by newline to PTY stdin."""
        self.write((text + "\n").encode())

    def forward_signal(self, sig: signal.Signals) -> None:
        """Forward a signal to the child process (e.g. SIGINT for Ctrl+C)."""
        if self._process and self._process.isalive():
            os.kill(self._process.pid, sig)

    def stop(self, timeout: float = 5.0) -> None:
        """Gracefully stop child; force-kill after timeout."""
        if not self._process or not self._process.isalive():
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=timeout)
        except Exception:
            self._process.terminate(force=True)

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.isalive()
```

- [ ] **Step 2: Commit**

```bash
git add t/pty_manager.py
git commit -m "feat: PTY manager for child CLI process lifecycle"
```

---

## Task 7: TUI

**Files:**
- Create: `t/tui.py`

- [ ] **Step 1: Implement tui.py**

```python
# t/tui.py
import asyncio
from typing import Callable, Awaitable
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

_STYLE = Style.from_dict({
    "status": "reverse",
    "output": "",
    "separator": "",
})

class TUI:
    """
    Full-screen TUI with:
    - Top: status bar
    - Middle: scrolling output buffer (translated CC output)
    - Bottom: single-line input field
    """

    def __init__(
        self,
        on_user_input: Callable[[str], Awaitable[None]],
        on_ctrl_c: Callable[[], None],
        on_exit: Callable[[], Awaitable[None]],
        cli_name: str = "claude",
    ):
        self._on_user_input = on_user_input
        self._on_ctrl_c = on_ctrl_c
        self._on_exit = on_exit
        self._cli_name = cli_name
        self._status = "starting"
        self._translating_info = ""

        # Output buffer (read-only scrolling area)
        self._output_buffer = Buffer(name="output", read_only=True)

        # Input buffer
        self._input_buffer = Buffer(name="input", multiline=False)

        kb = self._build_keybindings()

        layout = Layout(
            HSplit([
                Window(
                    content=FormattedTextControl(self._get_status_text),
                    height=1,
                    style="class:status",
                ),
                Window(
                    content=BufferControl(buffer=self._output_buffer, focusable=False),
                    wrap_lines=True,
                ),
                Window(height=1, char="─", style="class:separator"),
                Window(
                    content=BufferControl(buffer=self._input_buffer),
                    height=1,
                    get_line_prefix=lambda line_number, wrap_count: "> ",
                ),
            ])
        )

        self.app = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=True,
            style=_STYLE,
            mouse_support=False,
        )

    def _build_keybindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("enter")
        def _(event):
            text = self._input_buffer.text
            self._input_buffer.set_document(Document(""), bypass_readonly=True)
            asyncio.get_event_loop().create_task(self._on_user_input(text))

        @kb.add("c-c")
        def _(event):
            self._on_ctrl_c()

        @kb.add("c-d")
        def _(event):
            asyncio.get_event_loop().create_task(self._on_exit())

        return kb

    def _get_status_text(self):
        indicator = "● running" if self._status == "running" else "○ " + self._status
        suffix = f"  {self._translating_info}" if self._translating_info else ""
        return [("class:status", f" [T] {self._cli_name}  {indicator}{suffix} ")]

    def append_output(self, text: str) -> None:
        """Append text to the scrolling output area (thread-safe via call_from_executor)."""
        def _append():
            current = self._output_buffer.text
            new_text = current + text + "\n"
            self._output_buffer.set_document(
                Document(new_text, cursor_position=len(new_text)),
                bypass_readonly=True,
            )
        self.app.loop.call_soon_threadsafe(self.app.invalidate)
        asyncio.get_event_loop().call_soon(_append)

    def set_status(self, status: str) -> None:
        self._status = status
        self.app.invalidate()

    def set_translating(self, info: str) -> None:
        self._translating_info = info
        self.app.invalidate()

    async def run_async(self) -> None:
        await self.app.run_async()

    def exit(self) -> None:
        self.app.exit()
```

- [ ] **Step 2: Commit**

```bash
git add t/tui.py
git commit -m "feat: prompt_toolkit TUI with status bar and scrolling output"
```

---

## Task 8: Main Entry Point

**Files:**
- Create: `t/main.py`

- [ ] **Step 1: Implement main.py**

```python
# t/main.py
import asyncio
import signal
import sys
from pathlib import Path

from .config import load_config, default_config_path, Config
from .output_parser import OutputParser, ChunkType
from .translator import TranslatorClient
from .queue import TranslationQueue, QueueItem
from .pty_manager import PTYManager
from .tui import TUI

# Built-in commands handled by T (not forwarded to CC)
_BUILTIN_COMMANDS = {"/exit", "/restart", "/lang", "/config"}

class AgentT:
    def __init__(self, config: Config):
        self._config = config
        self._translator = TranslatorClient(config.translator)
        self._pty = PTYManager(config.cli.command, config.cli.args)
        self._parser = OutputParser()
        self._translation_enabled = True
        self._pending_chunks = 0

        self._queue = TranslationQueue(
            translate_fn=self._translate_to_zh,
            on_result=self._on_translated,
        )
        self._tui = TUI(
            on_user_input=self._handle_user_input,
            on_ctrl_c=self._handle_ctrl_c,
            on_exit=self._handle_exit,
            cli_name=config.cli.command,
        )

    async def _translate_to_zh(self, text: str) -> str:
        if not self._translation_enabled:
            return text
        return await self._translator.translate(text, target_lang="zh")

    def _on_translated(self, seq: int, text: str, is_code: bool) -> None:
        self._pending_chunks = max(0, self._pending_chunks - 1)
        if self._pending_chunks == 0:
            self._tui.set_translating("")
        self._tui.append_output(text)

    async def _handle_user_input(self, text: str) -> None:
        text = text.strip()
        if not text:
            return

        # Handle built-in commands
        cmd = text.split()[0].lower()
        if cmd == "/exit":
            await self._handle_exit()
            return
        if cmd == "/restart":
            self._pty.stop()
            self._pty.start()
            self._tui.append_output("[T] CC restarted.")
            return
        if cmd == "/lang":
            arg = text.split()[1].lower() if len(text.split()) > 1 else "toggle"
            if arg == "off":
                self._translation_enabled = False
                self._tui.append_output("[T] Translation disabled (raw mode).")
            else:
                self._translation_enabled = True
                self._tui.append_output("[T] Translation enabled.")
            return
        if cmd == "/config":
            c = self._config
            self._tui.append_output(
                f"[T] Config:\n"
                f"  provider: {c.translator.provider}\n"
                f"  model: {c.translator.model}\n"
                f"  cli: {c.cli.command}\n"
                f"  translation: {'on' if self._translation_enabled else 'off'}"
            )
            return

        # Translate Chinese input to English and send to CC
        english = await self._translator.translate(text, target_lang="en")
        self._pty.write_line(english)

    def _handle_ctrl_c(self) -> None:
        self._pty.forward_signal(signal.SIGINT)

    async def _handle_exit(self) -> None:
        self._pty.stop()
        await self._translator.close()
        self._tui.exit()

    async def _read_pty_loop(self) -> None:
        """Read PTY output, parse, enqueue for translation."""
        raw_buf = b""
        while self._pty.is_alive:
            try:
                data = await asyncio.wait_for(
                    self._pty.read(), timeout=self._config.translator.accumulate_timeout
                )
                if not data:
                    break
                raw_buf += data
                while b"\n" in raw_buf:
                    line_bytes, raw_buf = raw_buf.split(b"\n", 1)
                    line = line_bytes.decode("utf-8", errors="replace")
                    chunks = self._parser.feed_line(line)
                    for chunk in chunks:
                        self._pending_chunks += 1
                        self._tui.set_translating(f"translating…")
                        await self._queue.enqueue(
                            QueueItem(seq=chunk.seq, text=chunk.content, is_code=(chunk.type == ChunkType.CODE))
                        )
            except asyncio.TimeoutError:
                # Flush accumulated text on timeout
                for chunk in self._parser.flush():
                    self._pending_chunks += 1
                    await self._queue.enqueue(
                        QueueItem(seq=chunk.seq, text=chunk.content, is_code=False)
                    )

        # Process exited
        self._tui.set_status("stopped")

    async def run(self) -> None:
        self._pty.start()
        self._tui.set_status("running")
        asyncio.create_task(self._read_pty_loop())
        await self._tui.run_async()

def main() -> None:
    config_path = default_config_path()
    if not config_path.exists():
        print(f"Config not found at {config_path}")
        print("Create it with:\n")
        print("  mkdir -p ~/.t && cat > ~/.t/config.yaml << 'EOF'")
        print("translator:")
        print("  provider: openai")
        print("  api_key: YOUR_KEY")
        print("  model: gpt-4o")
        print("cli:")
        print("  command: claude")
        print("EOF")
        sys.exit(1)

    config = load_config(config_path)
    agent = AgentT(config)
    asyncio.run(agent.run())

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test**

Run: `pip install -e .`

Create `~/.t/config.yaml` with your real API key and translator config.

Run: `t`

Expected: TUI launches, `claude` starts in the background. Type a Chinese sentence, it should appear translated in the output area in Chinese.

- [ ] **Step 3: Test built-in commands**

- Type `/config` → should print current config
- Type `/lang off` → translation disabled message
- Type `/lang on` → translation enabled message
- Type `/restart` → CC restarts
- Press Ctrl+C → CC receives interrupt, T stays alive
- Type `/exit` → both T and CC exit cleanly

- [ ] **Step 4: Commit**

```bash
git add t/main.py
git commit -m "feat: main entry point wiring all components into AgentT"
```

---

## Self-Review

### Spec Coverage

| Requirement | Task |
|-------------|------|
| Chinese → English input translation | Task 8 `_handle_user_input` |
| English → Chinese output translation | Tasks 4, 5 |
| Code blocks pass through verbatim | Task 3, 5 `is_code` path |
| PTY-based CC lifecycle control | Task 6 |
| Real-time streaming output | Task 8 `_read_pty_loop` |
| Accumulate timeout (configurable) | Tasks 2, 8 |
| OpenAI API format | Task 4 `_call_openai` |
| Anthropic API format | Task 4 `_call_anthropic` |
| Custom base_url | Task 4, tested |
| Fallback on translation timeout | Task 4 |
| Ordered output guarantee | Task 5 |
| ANSI stripping | Task 3 `strip_ansi` |
| `/exit`, `/restart`, `/lang`, `/config` commands | Task 8 |
| Ctrl+C forwarded to CC | Task 7, 8 |
| Config file at `~/.t/config.yaml` | Task 2 |
| TUI with input box + scrolling output | Task 7 |

No gaps found.

### Placeholder Scan

No TBD, TODO, or placeholder patterns found.

### Type Consistency

- `Chunk` defined in Task 3, used correctly in Task 8 (`chunk.seq`, `chunk.content`, `chunk.type`)
- `QueueItem` defined in Task 5, used correctly in Task 8
- `TranslatorConfig` fields match usage in Task 4
- `PTYManager.write_line()` defined in Task 6, called in Task 8
