# t/tui.py
from __future__ import annotations
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
    - Top: status bar (shows CLI name + running state)
    - Middle: scrolling output buffer (translated CC output)
    - Bottom: single-line input field with "> " prompt
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
        """Append a line to the scrolling output area."""
        current = self._output_buffer.text
        new_text = current + text + "\n"
        self._output_buffer.set_document(
            Document(new_text, cursor_position=len(new_text)),
            bypass_readonly=True,
        )
        if self.app.is_running:
            self.app.invalidate()

    def set_status(self, status: str) -> None:
        self._status = status
        if self.app.is_running:
            self.app.invalidate()

    def set_translating(self, info: str) -> None:
        self._translating_info = info
        if self.app.is_running:
            self.app.invalidate()

    async def run_async(self) -> None:
        await self.app.run_async()

    def exit(self) -> None:
        self.app.exit()
