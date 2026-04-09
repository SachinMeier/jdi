from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the YAML configuration is invalid."""


@dataclass(frozen=True)
class AudioConfig:
    sample_rate_hz: int = 16_000
    block_size_frames: int = 1_280
    channels: int = 1
    device: str | int | None = None
    command_timeout_seconds: float = 4.0
    post_wake_delay_seconds: float = 0.3


@dataclass(frozen=True)
class RecognitionConfig:
    model_path: Path
    allow_unknown: bool = True


@dataclass(frozen=True)
class WakeWordConfig:
    enabled: bool = False
    model_names: tuple[str, ...] = ("hey jarvis",)
    model_paths: tuple[str, ...] = ()
    threshold: float = 0.5
    patience_frames: int = 1
    debounce_seconds: float = 1.0
    vad_threshold: float = 0.0
    enable_speex_noise_suppression: bool = False
    inference_framework: str = "onnx"
    custom_verifier_models: dict[str, str] = field(default_factory=dict)
    custom_verifier_threshold: float = 0.3


@dataclass(frozen=True)
class PushToTalkConfig:
    enabled: bool = False
    mode: str = "gpio"
    gpio_pin: int = 17
    hold_to_listen: bool = True
    pull_up: bool = True
    bounce_time_seconds: float = 0.05
    keyboard_key: str = "space"


@dataclass(frozen=True)
class LifxLanConfig:
    discovery_cache_seconds: float = 30.0
    verbose: bool = False


@dataclass(frozen=True)
class LifxHttpConfig:
    enabled: bool = False
    base_url: str = "https://api.lifx.com/v1"
    token_env_var: str = "LIFX_TOKEN"


@dataclass(frozen=True)
class LifxConfig:
    default_transport: str = "lan"
    lan: LifxLanConfig = field(default_factory=LifxLanConfig)
    http: LifxHttpConfig = field(default_factory=LifxHttpConfig)


@dataclass(frozen=True)
class LightDefinition:
    label: str
    http_selector: str | None = None

    def selector(self) -> str:
        return self.http_selector or f"label:{self.label}"


@dataclass(frozen=True)
class LightState:
    power: str | None = None
    brightness_pct: float | None = None
    kelvin: int | None = None
    hue_deg: float | None = None
    saturation_pct: float | None = None
    duration_seconds: float = 0.5

    def has_color_change(self) -> bool:
        return any(
            value is not None
            for value in (
                self.brightness_pct,
                self.kelvin,
                self.hue_deg,
                self.saturation_pct,
            )
        )


@dataclass(frozen=True)
class LocalSceneStep:
    target: str
    state: LightState


@dataclass(frozen=True)
class LocalScene:
    name: str
    description: str
    steps: tuple[LocalSceneStep, ...]


@dataclass(frozen=True)
class CommandAction:
    type: str
    target: str | None = None
    value: str | None = None
    transport: str | None = None
    selector: str | None = None
    scene: str | None = None
    scene_id: str | None = None
    duration_seconds: float = 0.5


@dataclass(frozen=True)
class CommandBinding:
    phrases: tuple[str, ...]
    action: CommandAction
    description: str = ""


@dataclass(frozen=True)
class AppConfig:
    config_path: Path
    audio: AudioConfig
    recognition: RecognitionConfig
    wake_word: WakeWordConfig
    push_to_talk: PushToTalkConfig
    lifx: LifxConfig
    lights: dict[str, LightDefinition]
    scenes: dict[str, LocalScene]
    commands: tuple[CommandBinding, ...]


_TRANSPORTS = {"lan", "http"}
_ACTION_TYPES = {"power", "local_scene", "http_scene"}
_POWER_VALUES = {"on", "off"}
_PUSH_TO_TALK_MODES = {"gpio", "keyboard"}


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    if not config_path.exists():
        raise ConfigError(f"Config file does not exist: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise ConfigError("Top-level YAML structure must be a mapping.")

    audio = _load_audio_config(raw.get("audio", {}))
    recognition = _load_recognition_config(raw.get("recognition", {}), config_path)
    wake_word = _load_wake_word_config(raw.get("wake_word", {}))
    push_to_talk = _load_push_to_talk_config(raw.get("push_to_talk", {}))
    lifx = _load_lifx_config(raw.get("lifx", {}))
    lights = _load_lights(raw.get("lights", {}))
    scenes = _load_scenes(raw.get("scenes", {}))
    commands = _load_commands(raw.get("commands", []))

    config = AppConfig(
        config_path=config_path,
        audio=audio,
        recognition=recognition,
        wake_word=wake_word,
        push_to_talk=push_to_talk,
        lifx=lifx,
        lights=lights,
        scenes=scenes,
        commands=commands,
    )
    _validate_config(config)
    return config


def _load_audio_config(raw: Any) -> AudioConfig:
    if not isinstance(raw, dict):
        raise ConfigError("`audio` must be a mapping.")
    return AudioConfig(
        sample_rate_hz=int(raw.get("sample_rate_hz", 16_000)),
        block_size_frames=int(raw.get("block_size_frames", 1_280)),
        channels=int(raw.get("channels", 1)),
        device=raw.get("device"),
        command_timeout_seconds=float(raw.get("command_timeout_seconds", 4.0)),
        post_wake_delay_seconds=float(raw.get("post_wake_delay_seconds", 0.3)),
    )


def _load_recognition_config(raw: Any, config_path: Path) -> RecognitionConfig:
    if not isinstance(raw, dict):
        raise ConfigError("`recognition` must be a mapping.")
    model_path_value = raw.get("model_path")
    if not model_path_value:
        raise ConfigError("`recognition.model_path` is required.")
    model_path = Path(model_path_value).expanduser()
    if not model_path.is_absolute():
        model_path = (config_path.parent / model_path).resolve()
    return RecognitionConfig(
        model_path=model_path,
        allow_unknown=bool(raw.get("allow_unknown", True)),
    )


def _load_wake_word_config(raw: Any) -> WakeWordConfig:
    if not isinstance(raw, dict):
        raise ConfigError("`wake_word` must be a mapping.")
    return WakeWordConfig(
        enabled=bool(raw.get("enabled", False)),
        model_names=tuple(raw.get("model_names", ["hey jarvis"])),
        model_paths=tuple(raw.get("model_paths", [])),
        threshold=float(raw.get("threshold", 0.5)),
        patience_frames=int(raw.get("patience_frames", 1)),
        debounce_seconds=float(raw.get("debounce_seconds", 1.0)),
        vad_threshold=float(raw.get("vad_threshold", 0.0)),
        enable_speex_noise_suppression=bool(
            raw.get("enable_speex_noise_suppression", False)
        ),
        inference_framework=str(raw.get("inference_framework", "onnx")),
        custom_verifier_models=dict(raw.get("custom_verifier_models", {})),
        custom_verifier_threshold=float(raw.get("custom_verifier_threshold", 0.3)),
    )


def _load_push_to_talk_config(raw: Any) -> PushToTalkConfig:
    if not isinstance(raw, dict):
        raise ConfigError("`push_to_talk` must be a mapping.")
    return PushToTalkConfig(
        enabled=bool(raw.get("enabled", False)),
        mode=str(raw.get("mode", "gpio")).strip().lower(),
        gpio_pin=int(raw.get("gpio_pin", 17)),
        hold_to_listen=bool(raw.get("hold_to_listen", True)),
        pull_up=bool(raw.get("pull_up", True)),
        bounce_time_seconds=float(raw.get("bounce_time_seconds", 0.05)),
        keyboard_key=str(raw.get("keyboard_key", "space")).strip().lower(),
    )


def _load_lifx_config(raw: Any) -> LifxConfig:
    if not isinstance(raw, dict):
        raise ConfigError("`lifx` must be a mapping.")
    lan_raw = raw.get("lan", {})
    http_raw = raw.get("http", {})
    if not isinstance(lan_raw, dict) or not isinstance(http_raw, dict):
        raise ConfigError("`lifx.lan` and `lifx.http` must be mappings.")
    return LifxConfig(
        default_transport=str(raw.get("default_transport", "lan")),
        lan=LifxLanConfig(
            discovery_cache_seconds=float(lan_raw.get("discovery_cache_seconds", 30.0)),
            verbose=bool(lan_raw.get("verbose", False)),
        ),
        http=LifxHttpConfig(
            enabled=bool(http_raw.get("enabled", False)),
            base_url=str(http_raw.get("base_url", "https://api.lifx.com/v1")).rstrip("/"),
            token_env_var=str(http_raw.get("token_env_var", "LIFX_TOKEN")),
        ),
    )


def _load_lights(raw: Any) -> dict[str, LightDefinition]:
    if not isinstance(raw, dict):
        raise ConfigError("`lights` must be a mapping.")
    lights: dict[str, LightDefinition] = {}
    for alias, value in raw.items():
        if not isinstance(value, dict):
            raise ConfigError(f"`lights.{alias}` must be a mapping.")
        label = value.get("label")
        if not label:
            raise ConfigError(f"`lights.{alias}.label` is required.")
        lights[str(alias)] = LightDefinition(
            label=str(label),
            http_selector=value.get("http_selector"),
        )
    return lights


def _load_scenes(raw: Any) -> dict[str, LocalScene]:
    if not isinstance(raw, dict):
        raise ConfigError("`scenes` must be a mapping.")
    scenes: dict[str, LocalScene] = {}
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise ConfigError(f"`scenes.{name}` must be a mapping.")
        steps_raw = value.get("steps", [])
        if not isinstance(steps_raw, list) or not steps_raw:
            raise ConfigError(f"`scenes.{name}.steps` must be a non-empty list.")
        steps = tuple(_load_scene_step(name, item) for item in steps_raw)
        scenes[str(name)] = LocalScene(
            name=str(name),
            description=str(value.get("description", name)),
            steps=steps,
        )
    return scenes


def _load_scene_step(scene_name: str, raw: Any) -> LocalSceneStep:
    if not isinstance(raw, dict):
        raise ConfigError(f"Scene step in `{scene_name}` must be a mapping.")
    target = raw.get("target")
    if not target:
        raise ConfigError(f"Every scene step in `{scene_name}` requires `target`.")
    return LocalSceneStep(target=str(target), state=_load_light_state(raw))


def _load_commands(raw: Any) -> tuple[CommandBinding, ...]:
    if not isinstance(raw, list) or not raw:
        raise ConfigError("`commands` must be a non-empty list.")
    commands: list[CommandBinding] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"`commands[{index}]` must be a mapping.")
        phrases_value = item.get("phrases")
        phrase_value = item.get("phrase")
        if phrases_value is None and phrase_value is not None:
            phrases_value = [phrase_value]
        if not isinstance(phrases_value, list) or not phrases_value:
            raise ConfigError(
                f"`commands[{index}]` requires `phrases` as a non-empty list."
            )
        action_raw = item.get("action")
        if not isinstance(action_raw, dict):
            raise ConfigError(f"`commands[{index}].action` must be a mapping.")
        commands.append(
            CommandBinding(
                phrases=tuple(str(value) for value in phrases_value),
                action=_load_command_action(action_raw),
                description=str(item.get("description", "")),
            )
        )
    return tuple(commands)


def _load_command_action(raw: dict[str, Any]) -> CommandAction:
    action_type = str(raw.get("type", "")).strip()
    return CommandAction(
        type=action_type,
        target=raw.get("target"),
        value=_power_or_none(raw.get("value")),
        transport=raw.get("transport"),
        selector=raw.get("selector"),
        scene=raw.get("scene"),
        scene_id=raw.get("scene_id"),
        duration_seconds=float(raw.get("duration_seconds", 0.5)),
    )


def _load_light_state(raw: dict[str, Any]) -> LightState:
    state = LightState(
        power=_power_or_none(raw.get("power")),
        brightness_pct=_float_or_none(raw.get("brightness_pct")),
        kelvin=_int_or_none(raw.get("kelvin")),
        hue_deg=_float_or_none(raw.get("hue_deg")),
        saturation_pct=_float_or_none(raw.get("saturation_pct")),
        duration_seconds=float(raw.get("duration_seconds", 0.5)),
    )
    _validate_light_state(state)
    return state


def _validate_config(config: AppConfig) -> None:
    if config.audio.sample_rate_hz != 16_000:
        raise ConfigError("This project currently expects 16 kHz mono microphone input.")
    if config.audio.channels != 1:
        raise ConfigError("This project currently expects a single microphone channel.")
    if config.audio.block_size_frames <= 0:
        raise ConfigError("`audio.block_size_frames` must be greater than zero.")
    if config.lifx.default_transport not in _TRANSPORTS:
        raise ConfigError("`lifx.default_transport` must be `lan` or `http`.")
    if config.wake_word.enabled and config.push_to_talk.enabled:
        raise ConfigError("Enable either `wake_word` or `push_to_talk`, not both.")
    if config.wake_word.inference_framework not in {"onnx", "tflite"}:
        raise ConfigError("`wake_word.inference_framework` must be `onnx` or `tflite`.")
    if (
        config.wake_word.patience_frames > 1
        and config.wake_word.debounce_seconds > 0
    ):
        raise ConfigError(
            "`wake_word.patience_frames` and `wake_word.debounce_seconds` cannot both be enabled."
        )
    if config.push_to_talk.mode not in _PUSH_TO_TALK_MODES:
        raise ConfigError("`push_to_talk.mode` must be `gpio` or `keyboard`.")
    if config.push_to_talk.mode == "keyboard" and not config.push_to_talk.keyboard_key:
        raise ConfigError("`push_to_talk.keyboard_key` may not be empty in keyboard mode.")

    seen_phrases: dict[str, str] = {}
    for command in config.commands:
        _validate_action(command.action, config)
        for phrase in command.phrases:
            normalized = normalize_phrase(phrase)
            if not normalized:
                raise ConfigError("Command phrases may not be empty after normalization.")
            if normalized in seen_phrases:
                raise ConfigError(
                    f"Duplicate normalized phrase `{normalized}` in commands."
                )
            seen_phrases[normalized] = phrase

    for scene in config.scenes.values():
        for step in scene.steps:
            _validate_target(step.target, config, context=f"scene `{scene.name}`")


def _validate_action(action: CommandAction, config: AppConfig) -> None:
    if action.type not in _ACTION_TYPES:
        raise ConfigError(
            f"Unknown action type `{action.type}`. Expected one of {_ACTION_TYPES}."
        )
    if action.duration_seconds < 0:
        raise ConfigError("Action durations must be non-negative.")
    if action.type == "power":
        if not action.target and not action.selector:
            raise ConfigError("Power actions require `target` or `selector`.")
        if action.value not in _POWER_VALUES:
            raise ConfigError("Power actions require `value` to be `on` or `off`.")
        transport = action.transport or config.lifx.default_transport
        if transport not in _TRANSPORTS:
            raise ConfigError("Power action transport must be `lan` or `http`.")
        if transport == "lan" and not action.target:
            raise ConfigError("LAN power actions require a configured `target` light alias.")
        if action.target:
            _validate_target(action.target, config, context="power action")
    elif action.type == "local_scene":
        if not action.scene:
            raise ConfigError("Local scene actions require `scene`.")
        if action.scene not in config.scenes:
            raise ConfigError(f"Unknown local scene `{action.scene}`.")
    elif action.type == "http_scene":
        if not config.lifx.http.enabled:
            raise ConfigError(
                "HTTP scene actions require `lifx.http.enabled: true`."
            )
        if not action.scene_id:
            raise ConfigError("HTTP scene actions require `scene_id`.")


def _validate_target(target: str, config: AppConfig, context: str) -> None:
    if target == "all":
        return
    if target not in config.lights:
        raise ConfigError(f"Unknown light target `{target}` in {context}.")


def _validate_light_state(state: LightState) -> None:
    if state.power is not None and state.power not in _POWER_VALUES:
        raise ConfigError("Scene step `power` must be `on` or `off`.")
    if state.brightness_pct is not None and not 0 <= state.brightness_pct <= 100:
        raise ConfigError("`brightness_pct` must be between 0 and 100.")
    if state.saturation_pct is not None and not 0 <= state.saturation_pct <= 100:
        raise ConfigError("`saturation_pct` must be between 0 and 100.")
    if state.kelvin is not None and not 1_500 <= state.kelvin <= 9_000:
        raise ConfigError("`kelvin` must be between 1500 and 9000.")
    if state.hue_deg is not None and not 0 <= state.hue_deg <= 360:
        raise ConfigError("`hue_deg` must be between 0 and 360.")
    if state.duration_seconds < 0:
        raise ConfigError("Scene step durations must be non-negative.")


def normalize_phrase(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _float_or_none(value: Any) -> float | None:
    return None if value is None else float(value)


def _int_or_none(value: Any) -> int | None:
    return None if value is None else int(value)


def _power_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if value is True:
        return "on"
    if value is False:
        return "off"
    return str(value).strip().lower()
