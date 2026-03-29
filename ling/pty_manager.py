# t/pty_manager.py
from __future__ import annotations
import asyncio
import os
import signal
import termios
from ptyprocess import PtyProcess
from .log import log


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
        # Disable terminal echo so input written to PTY isn't echoed back as output
        attrs = termios.tcgetattr(self._process.fd)
        attrs[3] &= ~termios.ECHO
        termios.tcsetattr(self._process.fd, termios.TCSANOW, attrs)
        log.debug(f"[pty] echo disabled")

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
        """Write a line of text followed by carriage return to PTY stdin."""
        log.debug(f"[pty] → 发送给codex: {repr(text)}")
        self.write((text + "\r").encode())

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
