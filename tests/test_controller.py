import textwrap
from pathlib import Path

import pytest

from jdi_voice.config import load_config
from jdi_voice.controller import CommandDispatcher


class _FakeLanClient:
    def __init__(self, discovery_cache_seconds: float, verbose: bool) -> None:
        self.calls: list[tuple[str, str, float]] = []
        self.scene_steps: list[tuple[str, str, object]] = []

    def set_power(self, label: str, power: str, duration_seconds: float = 0.5) -> None:
        self.calls.append((label, power, duration_seconds))

    def set_power_all(self, power: str, duration_seconds: float = 0.5) -> None:
        self.calls.append(("all", power, duration_seconds))

    def apply_state(self, label: str, state) -> None:
        self.scene_steps.append(("one", label, state))

    def apply_state_all(self, state) -> None:
        self.scene_steps.append(("all", "all", state))


class _FakeHttpClient:
    def __init__(self, token_env_var: str, base_url: str) -> None:
        self.token_env_var = token_env_var
        self.base_url = base_url

    def list_lights(self) -> list[dict[str, str]]:
        return [{"label": "Bedroom", "id": "light-1"}]

    def list_scenes(self) -> list[dict[str, str]]:
        return [{"name": "Movie Time", "uuid": "scene-1"}]


def test_http_token_is_not_required_for_lan_only_dispatch(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            recognition:
              model_path: ../models/vosk-model-small-en-us-0.15
            lifx:
              default_transport: lan
              http:
                enabled: true
                token_env_var: LIFX_TOKEN
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
                  transport: lan
            """
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.delenv("LIFX_TOKEN", raising=False)
    monkeypatch.setattr("jdi_voice.controller.LifxLanClient", _FakeLanClient)

    config = load_config(config_path)
    dispatcher = CommandDispatcher(config)
    result = dispatcher.dispatch(config.commands[0])

    assert result.details == "Set `Bedroom` to on over LAN."


def test_http_light_listing_initializes_client(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            recognition:
              model_path: ../models/vosk-model-small-en-us-0.15
            lifx:
              http:
                enabled: true
                token_env_var: LIFX_TOKEN
            lights: {}
            scenes: {}
            commands:
              - phrases: ["dummy"]
                action:
                  type: http_scene
                  scene_id: abc
            """
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("LIFX_TOKEN", "secret-token")
    monkeypatch.setattr("jdi_voice.controller.LifxLanClient", _FakeLanClient)
    monkeypatch.setattr("jdi_voice.controller.LifxHttpClient", _FakeHttpClient)

    config = load_config(config_path)
    dispatcher = CommandDispatcher(config)

    assert dispatcher.list_lights("http") == ["Bedroom (light-1)"]
    assert dispatcher.list_http_scenes() == ["Movie Time (scene-1)"]


def test_http_listing_fails_cleanly_when_http_disabled(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            recognition:
              model_path: ../models/vosk-model-small-en-us-0.15
            lights: {}
            scenes: {}
            commands:
              - phrases: ["dummy"]
                action:
                  type: power
                  target: all
                  value: on
            """
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr("jdi_voice.controller.LifxLanClient", _FakeLanClient)

    config = load_config(config_path)
    dispatcher = CommandDispatcher(config)

    with pytest.raises(Exception, match="HTTP transport is not enabled in config"):
        dispatcher.list_lights("http")


def test_local_scene_dispatches_each_step_in_order(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            recognition:
              model_path: ../models/vosk-model-small-en-us-0.15
            lights:
              bedroom:
                label: Bedroom
              hallway:
                label: Hallway
            scenes:
              bedtime:
                steps:
                  - target: bedroom
                    power: on
                    brightness_pct: 10
                  - target: all
                    power: off
            commands:
              - phrases: ["bedtime"]
                action:
                  type: local_scene
                  scene: bedtime
            """
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr("jdi_voice.controller.LifxLanClient", _FakeLanClient)

    config = load_config(config_path)
    dispatcher = CommandDispatcher(config)
    result = dispatcher.dispatch(config.commands[0])

    assert result.details == "Applied local scene `bedtime` with 2 step(s)."
    assert dispatcher._lan_client.scene_steps[0][0:2] == ("one", "Bedroom")
    assert dispatcher._lan_client.scene_steps[1][0:2] == ("all", "all")
