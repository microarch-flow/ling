# Agent T — Design Document

**Date:** 2026-03-28
**Status:** Approved

## Overview

Agent T is a CLI tool that wraps Claude Code (CC) or Codex CLI with a real-time bilingual translation layer. The user interacts in Chinese; T translates input to English before passing it to CC, and translates CC's non-code output back to Chinese in real-time.

T is a stateless translation proxy. Session continuity and context management are handled entirely by the underlying CLI tool.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                  Agent T                     │
│                                              │
│  ┌──────────┐    ┌──────────┐    ┌────────┐ │
│  │  TUI     │    │Translator│    │ PTY    │ │
│  │(prompt_  │◄──►│ Client   │◄──►│Manager │ │
│  │ toolkit) │    │(async)   │    │        │ │
│  └──────────┘    └──────────┘    └────┬───┘ │
│                                       │PTY  │
└───────────────────────────────────────┼─────┘
                                        │
                                   ┌────▼────┐
                                   │   CC    │
                                   │(claude/ │
                                   │ codex)  │
                                   └─────────┘
```

### Modules

- **TUI** (`prompt_toolkit`): Bottom-fixed input box, scrolling output area above. Displays translated Chinese output.
- **Translator Client** (async): Calls third-party translation LLM. Supports OpenAI and Anthropic API formats. Configurable provider, model, base_url.
- **PTY Manager** (`ptyprocess`): Launches and owns the CC process with a PTY allocation. Handles lifecycle (start, graceful stop, force kill) and raw I/O.

---

## Configuration

File location: `~/.t/config.yaml`

```yaml
translator:
  provider: openai          # openai | anthropic
  api_key: sk-xxx
  base_url: https://...     # optional, for third-party compatible endpoints
  model: gpt-4o
  accumulate_timeout: 2.0   # seconds to wait before sending chunk for translation
  request_timeout: 30       # translation API call timeout in seconds
  fallback_on_timeout: true # if true, show original text on timeout

cli:
  command: claude           # or codex, or any absolute path
  args: []                  # extra startup arguments
```

---

## Data Flow

### Input (User → CC)

```
User types Chinese input
  → Wait for full sentence (Enter key)
  → Send to translation LLM (synchronous, await full translation)
  → Write English translation to PTY stdin
  → CC receives and processes
```

### Output (CC → User)

```
PTY output stream
  → OutputParser (real-time scanning)
      ├── Code block detected (``` or indented block)
      │     → Buffer entire code block
      │     → Pass through as-is when complete (no translation)
      └── Plain text
            → Accumulate until: blank line OR accumulate_timeout exceeded
            → Enqueue to translation_queue

translation_queue (ordered async queue)
  → Translate chunks concurrently
  → Display results in original order (ordered output guarantee)
  → On timeout: display original text, continue
```

**ANSI escape codes** (colors, progress bars): stripped before translation, re-applied to translated output.

---

## PTY Lifecycle

### Startup

```
T starts
  → Load config.yaml
  → Initialize TUI
  → Launch CC via ptyprocess (PTY allocated)
  → Start asyncio event loop listening to PTY output
  → Wait for user input
```

### Shutdown

```
User types /exit or Ctrl+D
  → Send graceful exit signal to CC
  → Wait up to 5s for CC to exit
  → Force kill if timeout exceeded
  → Clean up PTY, exit T
```

### Error Handling

| Scenario | Behavior |
|----------|----------|
| CC crashes unexpectedly | TUI shows warning, prompts user to restart |
| Translation API unreachable | Fallback to original text, continue running |
| PTY read error | Retry 3 times, then prompt user |
| User presses Ctrl+C | Forward signal to CC (do NOT exit T) |

**Ctrl+C behavior**: T intercepts Ctrl+C and forwards it to CC. This allows the user to cancel CC's current task without exiting T.

---

## TUI Layout

```
┌─────────────────────────────────────┐
│ [T] claude  ● running        [?]help│  ← status bar
├─────────────────────────────────────┤
│                                     │
│  Scrolling output area              │
│  (code blocks verbatim,             │
│   plain text translated to Chinese) │
│                                     │
├─────────────────────────────────────┤
│ Translating… [████░░] 1/3 chunks   │  ← translation progress (optional)
├─────────────────────────────────────┤
│ > Input box (Chinese)               │  ← fixed bottom
└─────────────────────────────────────┘
```

### Built-in Commands (not forwarded to CC)

| Command | Effect |
|---------|--------|
| `/exit` | Gracefully exit T and CC |
| `/restart` | Restart the CC process |
| `/lang off` | Disable translation (raw mode) |
| `/lang on` | Re-enable translation |
| `/config` | Display current configuration |

---

## Technology Stack

| Component | Library |
|-----------|---------|
| Language | Python 3.11+ |
| TUI | `prompt_toolkit` |
| PTY management | `ptyprocess` |
| Async I/O | `asyncio` |
| Translation API | `httpx` (async HTTP) |
| Config | `pyyaml` |
