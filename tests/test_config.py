import textwrap
from pathlib import Path

import pytest

from jdi_voice.config import ConfigError, load_config


def test_load_config_resolves_relative_model_path(tmp_path: Path) -> None:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            recognition:
              model_path: ../models/vosk-model-small-en-us-0.15
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

    config = load_config(config_path)

    assert config.recognition.model_path == (
        (tmp_path / "../models/vosk-model-small-en-us-0.15").resolve()
    )


def test_duplicate_normalized_phrases_raise_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            recognition:
              model_path: ../models/vosk-model-small-en-us-0.15
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
              - phrases: ["Turn bedroom lights on!!!"]
                action:
                  type: power
                  target: bedroom
                  value: off
            """
        ).strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_scene_target_must_exist(tmp_path: Path) -> None:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            recognition:
              model_path: ../models/vosk-model-small-en-us-0.15
            lights:
              bedroom:
                label: Bedroom
            scenes:
              movie:
                steps:
                  - target: office
                    power: on
            commands:
              - phrases: ["movie time"]
                action:
                  type: local_scene
                  scene: movie
            """
        ).strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_selector_only_lan_power_action_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            recognition:
              model_path: ../models/vosk-model-small-en-us-0.15
            lifx:
              default_transport: lan
            lights: {}
            scenes: {}
            commands:
              - phrases: ["turn bedroom group on"]
                action:
                  type: power
                  selector: group:Bedroom
                  value: on
                  transport: lan
            """
        ).strip(),
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigError,
        match="LAN power actions require a configured `target` light alias.",
    ):
        load_config(config_path)


def test_keyboard_push_to_talk_mode_requires_non_empty_key(tmp_path: Path) -> None:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            recognition:
              model_path: ../models/vosk-model-small-en-us-0.15
            push_to_talk:
              enabled: true
              mode: keyboard
              keyboard_key: ""
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
            """
        ).strip(),
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigError,
        match="`push_to_talk.keyboard_key` may not be empty in keyboard mode.",
    ):
        load_config(config_path)


def test_wake_word_rejects_patience_plus_debounce(tmp_path: Path) -> None:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            recognition:
              model_path: ../models/vosk-model-small-en-us-0.15
            wake_word:
              enabled: true
              patience_frames: 2
              debounce_seconds: 1.0
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
            """
        ).strip(),
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigError,
        match="`wake_word.patience_frames` and `wake_word.debounce_seconds` cannot both be enabled.",
    ):
        load_config(config_path)
