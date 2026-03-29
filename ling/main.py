# t/main.py
from __future__ import annotations
import asyncio
import signal
import sys
from pathlib import Path

from .config import load_config, default_config_path, Config
from .output_parser import OutputParser, ChunkType, strip_ansi
from .translator import TranslatorClient
from .queue import TranslationQueue, QueueItem
from .pty_manager import PTYManager
from .tui import TUI
from .log import log

_BUILTIN_PREFIXES = {"/exit", "/restart", "/lang", "/config"}

# Inputs that should be forwarded to the CLI directly without translation.
# These are typically responses to interactive prompts (menu selections, confirmations).
_DIRECT_PASSTHROUGH = {"y", "n", "yes", "no", "q", "quit", "exit"}

def _is_direct_passthrough(text: str) -> bool:
    """Return True if input should bypass translation and go straight to the CLI."""
    t = text.strip().lower()
    # Single digit (menu selection: 1, 2, 3...)
    if len(t) == 1 and t.isdigit():
        return True
    # Common single-char confirmations
    if len(t) == 1 and t in ("y", "n", "q"):
        return True
    # Common words
    if t in _DIRECT_PASSTHROUGH:
        return True
    # Pure ASCII with no Chinese characters — likely already English or a command
    if t and all(ord(c) < 128 for c in t):
        return True
    return False

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
        log.debug(f"[output] 翻译后显示: seq={seq} is_code={is_code} text={repr(text[:120])}")
        self._pending_chunks = max(0, self._pending_chunks - 1)
        if self._pending_chunks == 0:
            self._tui.set_translating("")
        self._tui.append_output(text)

    async def _handle_user_input(self, text: str) -> None:
        log.debug(f"[input] received: {repr(text)}")
        text = text.strip()
        if not text:
            log.debug("[input] empty after strip, ignoring")
            return

        cmd = text.split()[0].lower()

        if cmd == "/exit":
            await self._handle_exit()
            return
        if cmd == "/restart":
            self._pty.stop()
            self._pty.start()
            self._tui.append_output("[ling] CC restarted.")
            return
        if cmd == "/lang":
            parts = text.split()
            arg = parts[1].lower() if len(parts) > 1 else "toggle"
            if arg == "off":
                self._translation_enabled = False
                self._tui.append_output("[ling] Translation disabled (raw mode).")
            else:
                self._translation_enabled = True
                self._tui.append_output("[ling] Translation enabled.")
            return
        if cmd == "/config":
            c = self._config
            self._tui.append_output(
                f"[ling] Config:\n"
                f"  provider: {c.translator.provider}\n"
                f"  model: {c.translator.model}\n"
                f"  cli: {c.cli.command}\n"
                f"  translation: {'on' if self._translation_enabled else 'off'}"
            )
            return

        # Short inputs are likely interactive CLI responses — forward directly
        if _is_direct_passthrough(text):
            log.debug(f"[input] 直接透传: {repr(text)}")
            self._pty.write_line(text)
            return

        # Translate Chinese input to English, send to CC
        import time
        log.debug(f"[input] 原文: {repr(text)}")
        t0 = time.monotonic()
        try:
            english = await self._translator.translate(text, target_lang="en")
        except Exception as e:
            log.error(f"[input] 翻译失败: {e}")
            self._tui.append_output(f"[ling] 翻译失败: {e}")
            return
        elapsed = time.monotonic() - t0
        log.debug(f"[input] 翻译结果({elapsed:.1f}s): {repr(english)}")
        self._pty.write_line(english)
        log.debug(f"[input] 已发送给 PTY")

    def _handle_ctrl_c(self) -> None:
        self._pty.forward_signal(signal.SIGINT)

    async def _handle_exit(self) -> None:
        self._pty.stop()
        await self._translator.close()
        self._tui.exit()

    async def _read_pty_loop(self) -> None:
        """
        Read PTY output using a producer thread + asyncio.Queue to avoid
        the run_in_executor / wait_for cancellation bug.
        """
        import threading
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _reader_thread():
            log.debug("[pty] reader thread started")
            while True:
                try:
                    data = self._pty._process.read(4096)
                    log.debug(f"[pty] read {len(data)} bytes")
                    loop.call_soon_threadsafe(queue.put_nowait, data)
                except EOFError:
                    log.debug("[pty] EOF")
                    loop.call_soon_threadsafe(queue.put_nowait, None)
                    break
                except Exception as e:
                    log.error(f"[pty] read error: {e}")
                    loop.call_soon_threadsafe(queue.put_nowait, None)
                    break

        threading.Thread(target=_reader_thread, daemon=True).start()

        raw_buf = b""
        last_data_time = loop.time()

        while True:
            try:
                data = await asyncio.wait_for(
                    queue.get(),
                    timeout=self._config.translator.accumulate_timeout,
                )
                if data is None:
                    break
                last_data_time = loop.time()
                raw_buf += data
                # Normalize \r\n and bare \r to \n
                raw_buf = raw_buf.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                log.debug(f"[pty] raw_buf={len(raw_buf)}B sample={repr(raw_buf[:80])}")
                while b"\n" in raw_buf:
                    line_bytes, raw_buf = raw_buf.split(b"\n", 1)
                    line = line_bytes.decode("utf-8", errors="replace")
                    log.debug(f"[pty] codex原文: {repr(line[:120])}")
                    for chunk in self._parser.feed_line(line):
                        log.debug(f"[pty] chunk seq={chunk.seq} type={chunk.type} skip={chunk.skip_translation}")
                        self._pending_chunks += 1
                        self._tui.set_translating("translating…")
                        await self._queue.enqueue(
                            QueueItem(
                                seq=chunk.seq,
                                text=chunk.content,
                                is_code=chunk.skip_translation,
                            )
                        )
            except asyncio.TimeoutError:
                # Flush raw_buf even if no newline found (TUI apps use ANSI, not newlines)
                if raw_buf:
                    text = strip_ansi(raw_buf.decode("utf-8", errors="replace")).strip()
                    log.debug(f"[pty] timeout flush raw_buf {len(raw_buf)}B → {repr(text[:120])}")
                    raw_buf = b""
                    if text:
                        for chunk in self._parser.feed_line(text):
                            self._pending_chunks += 1
                            self._tui.set_translating("translating…")
                            await self._queue.enqueue(
                                QueueItem(seq=chunk.seq, text=chunk.content, is_code=chunk.skip_translation)
                            )
                for chunk in self._parser.flush():
                    log.debug(f"[pty] flushed chunk seq={chunk.seq}")
                    self._pending_chunks += 1
                    await self._queue.enqueue(
                        QueueItem(seq=chunk.seq, text=chunk.content, is_code=chunk.skip_translation)
                    )

        log.debug("[pty] loop ended")
        self._tui.set_status("stopped")

    async def run(self) -> None:
        log.debug("[main] starting PTY")
        self._pty.start()
        log.debug(f"[main] PTY started, is_alive={self._pty.is_alive}")
        self._tui.set_status("running")
        asyncio.create_task(self._read_pty_loop())
        log.debug("[main] starting TUI")
        await self._tui.run_async()
        log.debug("[main] TUI exited")


def main() -> None:
    config_path = default_config_path()
    if not config_path.exists():
        print(f"Config not found at {config_path}")
        print("\nCreate it with:\n")
        print("  mkdir -p ~/.ling && cat > ~/.ling/config.yaml << 'EOF'")
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
