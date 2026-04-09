from __future__ import annotations

import os
import select
import sys
import termios
import tty


class PushToTalkError(RuntimeError):
    """Raised when a push-to-talk trigger cannot be initialized."""


class GpioPushToTalkButton:
    """GPIO button gate for Raspberry Pi hardware."""

    def __init__(
        self,
        gpio_pin: int,
        pull_up: bool = True,
        bounce_time_seconds: float = 0.05,
    ) -> None:
        try:
            from gpiozero import Button
        except ImportError as exc:
            raise PushToTalkError(
                "gpiozero is not installed. Install it if you want push-to-talk."
            ) from exc
        self._button = Button(
            gpio_pin,
            pull_up=pull_up,
            bounce_time=bounce_time_seconds,
        )

    @property
    def is_pressed(self) -> bool:
        return bool(self._button.is_pressed)


class TerminalKeyTrigger:
    """Press a terminal key to arm one command capture on macOS or Linux."""

    _SPECIAL_KEYS = {
        "space": " ",
        "enter": "\n",
        "return": "\n",
        "tab": "\t",
        "escape": "\x1b",
        "esc": "\x1b",
    }

    def __init__(self, key: str = "space") -> None:
        normalized_key = key.strip().lower()
        if not normalized_key:
            raise PushToTalkError("Keyboard push-to-talk key may not be empty.")
        if len(normalized_key) == 1:
            self._target = normalized_key
        elif normalized_key in self._SPECIAL_KEYS:
            self._target = self._SPECIAL_KEYS[normalized_key]
        else:
            raise PushToTalkError(
                f"Unsupported keyboard push-to-talk key `{key}`. "
                "Use a single character or one of: space, enter, tab, esc."
            )
        self._fd: int | None = None
        self._original_termios: list | None = None

    def __enter__(self) -> "TerminalKeyTrigger":
        if not sys.stdin.isatty():
            raise PushToTalkError(
                "Keyboard push-to-talk requires a foreground terminal (TTY)."
            )
        self._fd = sys.stdin.fileno()
        self._original_termios = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None and self._original_termios is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._original_termios)
        self._fd = None
        self._original_termios = None

    def wait_for_press(self, poll_interval_seconds: float = 0.1) -> None:
        if self._fd is None:
            raise PushToTalkError(
                "Keyboard push-to-talk trigger must be entered before use."
            )
        while True:
            readable, _, _ = select.select([self._fd], [], [], poll_interval_seconds)
            if not readable:
                continue
            char = os.read(self._fd, 1).decode(errors="ignore")
            if self._matches(char):
                return

    def _matches(self, char: str) -> bool:
        if self._target == "\n":
            return char in {"\n", "\r"}
        return char == self._target
