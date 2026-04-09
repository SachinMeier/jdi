from __future__ import annotations

import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from jdi_voice.config import load_config
from jdi_voice.service import VoiceAutomationService


class _StopService(RuntimeError):
    pass


class _FakeMicrophone:
    chunks: list[bytes] = []

    def __init__(self, *args, **kwargs) -> None:
        self._chunks = iter(type(self).chunks)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, timeout_seconds: float = 1.0) -> bytes:
        try:
            return next(self._chunks)
        except StopIteration as exc:
            raise _StopService() from exc


class _FakeSession:
    def __init__(self, transcripts_by_chunk: dict[bytes, str | None], final_text: str | None = None) -> None:
        self._transcripts_by_chunk = transcripts_by_chunk
        self._final_text = final_text

    def accept_audio(self, audio: bytes) -> str | None:
        return self._transcripts_by_chunk.get(audio)

    def finalize(self) -> str | None:
        return self._final_text


class _FakeRecognizer:
    session_payloads: list[tuple[dict[bytes, str | None], str | None]] = []

    def __init__(self, *args, **kwargs) -> None:
        self._session_payloads = list(type(self).session_payloads)

    def new_session(self) -> _FakeSession:
        if self._session_payloads:
            transcripts_by_chunk, final_text = self._session_payloads.pop(0)
        else:
            transcripts_by_chunk, final_text = ({}, None)
        return _FakeSession(transcripts_by_chunk, final_text)


class _FakeDispatcher:
    instance: _FakeDispatcher | None = None

    def __init__(self, config) -> None:
        self.commands = []
        type(self).instance = self

    def dispatch(self, command):
        self.commands.append(command)
        return SimpleNamespace(details=f"executed {command.phrases[0]}")


class _FakeWakeWordGate:
    instance: _FakeWakeWordGate | None = None

    def __init__(self, config) -> None:
        self.reset_calls = 0
        type(self).instance = self

    def process_audio(self, audio: bytes):
        if audio == b"wake":
            return SimpleNamespace(model_name="hey_jarvis", score=0.9)
        return None

    def reset(self) -> None:
        self.reset_calls += 1


class _FakePushToTalkButton:
    pressed_values: list[bool] = [True]

    def __init__(self, *args, **kwargs) -> None:
        self._pressed_values = iter(type(self).pressed_values)
        self._last = True

    @property
    def is_pressed(self) -> bool:
        try:
            self._last = next(self._pressed_values)
        except StopIteration:
            pass
        return self._last


class _FakeKeyboardTrigger:
    enter_count = 0
    wait_count = 0

    def __init__(self, key: str = "space") -> None:
        self.key = key

    def __enter__(self):
        type(self).enter_count += 1
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def wait_for_press(self, poll_interval_seconds: float = 0.1) -> None:
        type(self).wait_count += 1
        if type(self).wait_count > 1:
            raise _StopService()
        return None


def _write_config(tmp_path: Path, body: str) -> Path:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(textwrap.dedent(body).strip(), encoding="utf-8")
    return config_path


def test_run_always_listening_dispatches_matched_phrase(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        recognition:
          model_path: /unused/in-test
        lights:
          bedroom:
            label: Bedroom
        scenes: {}
        commands:
          - phrases: ["turn bedroom lights on"]
            action:
              type: power
              target: bedroom
              value: on
        """,
    )
    config = load_config(config_path)

    _FakeMicrophone.chunks = [b"noise", b"command"]
    _FakeRecognizer.session_payloads = [
        ({b"noise": None, b"command": "turn bedroom lights on"}, None),
        ({}, None),
    ]

    monkeypatch.setattr("jdi_voice.service.MicrophoneAudioSource", _FakeMicrophone)
    monkeypatch.setattr("jdi_voice.service.VoskPhraseRecognizer", _FakeRecognizer)
    monkeypatch.setattr("jdi_voice.service.CommandDispatcher", _FakeDispatcher)

    with pytest.raises(_StopService):
        VoiceAutomationService(config).run()

    assert _FakeDispatcher.instance is not None
    assert [command.phrases[0] for command in _FakeDispatcher.instance.commands] == [
        "turn bedroom lights on"
    ]


def test_run_wake_word_mode_waits_for_wake_then_dispatches(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        audio:
          post_wake_delay_seconds: 0.08
        recognition:
          model_path: /unused/in-test
        wake_word:
          enabled: true
        lights:
          bedroom:
            label: Bedroom
        scenes: {}
        commands:
          - phrases: ["turn bedroom lights on"]
            action:
              type: power
              target: bedroom
              value: on
        """,
    )
    config = load_config(config_path)

    _FakeMicrophone.chunks = [b"wake", b"discard", b"command"]
    _FakeRecognizer.session_payloads = [
        ({b"command": "turn bedroom lights on"}, None),
    ]

    monkeypatch.setattr("jdi_voice.service.MicrophoneAudioSource", _FakeMicrophone)
    monkeypatch.setattr("jdi_voice.service.VoskPhraseRecognizer", _FakeRecognizer)
    monkeypatch.setattr("jdi_voice.service.CommandDispatcher", _FakeDispatcher)
    monkeypatch.setattr("jdi_voice.service.OpenWakeWordGate", _FakeWakeWordGate)

    with pytest.raises(_StopService):
        VoiceAutomationService(config).run()

    assert _FakeDispatcher.instance is not None
    assert len(_FakeDispatcher.instance.commands) == 1
    assert _FakeWakeWordGate.instance is not None
    assert _FakeWakeWordGate.instance.reset_calls == 1


def test_run_push_to_talk_finalizes_after_button_release(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        recognition:
          model_path: /unused/in-test
        push_to_talk:
          enabled: true
        lights:
          bedroom:
            label: Bedroom
        scenes: {}
        commands:
          - phrases: ["turn bedroom lights on"]
            action:
              type: power
              target: bedroom
              value: on
        """,
    )
    config = load_config(config_path)

    _FakeMicrophone.chunks = [b"partial"]
    _FakeRecognizer.session_payloads = [
        ({b"partial": None}, "turn bedroom lights on"),
    ]
    _FakePushToTalkButton.pressed_values = [True, False]

    monkeypatch.setattr("jdi_voice.service.MicrophoneAudioSource", _FakeMicrophone)
    monkeypatch.setattr("jdi_voice.service.VoskPhraseRecognizer", _FakeRecognizer)
    monkeypatch.setattr("jdi_voice.service.CommandDispatcher", _FakeDispatcher)
    monkeypatch.setattr("jdi_voice.service.GpioPushToTalkButton", _FakePushToTalkButton)

    with pytest.raises(_StopService):
        VoiceAutomationService(config).run()

    assert _FakeDispatcher.instance is not None
    assert [command.phrases[0] for command in _FakeDispatcher.instance.commands] == [
        "turn bedroom lights on"
    ]


def test_run_keyboard_push_to_talk_arms_one_command(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        recognition:
          model_path: /unused/in-test
        push_to_talk:
          enabled: true
          mode: keyboard
          keyboard_key: space
        lights:
          bedroom:
            label: Bedroom
        scenes: {}
        commands:
          - phrases: ["turn bedroom lights on"]
            action:
              type: power
              target: bedroom
              value: on
        """,
    )
    config = load_config(config_path)

    _FakeMicrophone.chunks = [b"command"]
    _FakeRecognizer.session_payloads = [
        ({b"command": "turn bedroom lights on"}, None),
    ]
    _FakeKeyboardTrigger.enter_count = 0
    _FakeKeyboardTrigger.wait_count = 0

    monkeypatch.setattr("jdi_voice.service.MicrophoneAudioSource", _FakeMicrophone)
    monkeypatch.setattr("jdi_voice.service.VoskPhraseRecognizer", _FakeRecognizer)
    monkeypatch.setattr("jdi_voice.service.CommandDispatcher", _FakeDispatcher)
    monkeypatch.setattr("jdi_voice.service.TerminalKeyTrigger", _FakeKeyboardTrigger)

    with pytest.raises(_StopService):
        VoiceAutomationService(config).run()

    assert _FakeKeyboardTrigger.enter_count == 1
    assert _FakeKeyboardTrigger.wait_count >= 1
    assert _FakeDispatcher.instance is not None
    assert [command.phrases[0] for command in _FakeDispatcher.instance.commands] == [
        "turn bedroom lights on"
    ]
