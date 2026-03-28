# t/main.py
from __future__ import annotations
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

_BUILTIN_PREFIXES = {"/exit", "/restart", "/lang", "/config"}

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

        # Translate Chinese input to English, send to CC
        english = await self._translator.translate(text, target_lang="en")
        self._pty.write_line(english)

    def _handle_ctrl_c(self) -> None:
        self._pty.forward_signal(signal.SIGINT)

    async def _handle_exit(self) -> None:
        self._pty.stop()
        await self._translator.close()
        self._tui.exit()

    async def _read_pty_loop(self) -> None:
        raw_buf = b""
        while self._pty.is_alive:
            try:
                data = await asyncio.wait_for(
                    self._pty.read(),
                    timeout=self._config.translator.accumulate_timeout,
                )
                if not data:
                    break
                raw_buf += data
                while b"\n" in raw_buf:
                    line_bytes, raw_buf = raw_buf.split(b"\n", 1)
                    line = line_bytes.decode("utf-8", errors="replace")
                    for chunk in self._parser.feed_line(line):
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
                for chunk in self._parser.flush():
                    self._pending_chunks += 1
                    await self._queue.enqueue(
                        QueueItem(seq=chunk.seq, text=chunk.content, is_code=chunk.skip_translation)
                    )

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
