from __future__ import annotations

import logging
from dataclasses import dataclass

from .config import AppConfig, CommandBinding, LightState
from .lifx.http_client import LifxHttpClient, LifxHttpError
from .lifx.lan_client import LifxLanClient


@dataclass(frozen=True)
class DispatchResult:
    command_description: str
    details: str


class CommandDispatcher:
    """Executes matched phrases against the configured LIFX transports."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._logger = logging.getLogger(__name__)
        self._lan_client = LifxLanClient(
            discovery_cache_seconds=config.lifx.lan.discovery_cache_seconds,
            verbose=config.lifx.lan.verbose,
        )
        self._http_client: LifxHttpClient | None = None

    def dispatch(self, command: CommandBinding) -> DispatchResult:
        action = command.action
        if action.type == "power":
            return self._dispatch_power(command)
        if action.type == "local_scene":
            return self._dispatch_local_scene(command)
        if action.type == "http_scene":
            return self._dispatch_http_scene(command)
        raise RuntimeError(f"Unsupported action type: {action.type}")

    def list_lights(self, transport: str) -> list[str]:
        if transport == "lan":
            return [
                f"{light.label} ({light.identifier})"
                for light in self._lan_client.list_lights(force_refresh=True)
            ]
        if transport == "http":
            http_client = self._require_http_client()
            return [
                f"{light.get('label', '<unnamed>')} ({light.get('id', 'unknown')})"
                for light in http_client.list_lights()
            ]
        raise ValueError(f"Unknown transport `{transport}`.")

    def list_http_scenes(self) -> list[str]:
        scenes = self._require_http_client().list_scenes()
        return [f"{scene.get('name', '<unnamed>')} ({scene.get('uuid')})" for scene in scenes]

    def _dispatch_power(self, command: CommandBinding) -> DispatchResult:
        action = command.action
        transport = action.transport or self._config.lifx.default_transport
        if transport == "lan":
            if action.target == "all":
                self._lan_client.set_power_all(
                    power=action.value or "off",
                    duration_seconds=action.duration_seconds,
                )
                details = f"Set all LAN lights to {action.value}."
            else:
                light = self._resolve_light(action.target)
                self._lan_client.set_power(
                    label=light.label,
                    power=action.value or "off",
                    duration_seconds=action.duration_seconds,
                )
                details = f"Set `{light.label}` to {action.value} over LAN."
            return DispatchResult(command.description or command.phrases[0], details)

        if transport == "http":
            http_client = self._require_http_client()
            selector = action.selector or self._resolve_selector(action.target)
            http_client.set_power(
                selector=selector,
                power=action.value or "off",
                duration_seconds=action.duration_seconds,
            )
            return DispatchResult(
                command.description or command.phrases[0],
                f"Set selector `{selector}` to {action.value} over HTTP.",
            )
        raise RuntimeError(f"Unsupported transport `{transport}`.")

    def _dispatch_local_scene(self, command: CommandBinding) -> DispatchResult:
        scene_name = command.action.scene or ""
        scene = self._config.scenes[scene_name]
        for step in scene.steps:
            self._apply_scene_step(step.target, step.state)
        return DispatchResult(
            command.description or command.phrases[0],
            f"Applied local scene `{scene.name}` with {len(scene.steps)} step(s).",
        )

    def _dispatch_http_scene(self, command: CommandBinding) -> DispatchResult:
        http_client = self._require_http_client()
        http_client.activate_scene(
            scene_id=command.action.scene_id or "",
            duration_seconds=command.action.duration_seconds,
        )
        return DispatchResult(
            command.description or command.phrases[0],
            f"Activated HTTP scene `{command.action.scene_id}`.",
        )

    def _apply_scene_step(self, target: str, state: LightState) -> None:
        if target == "all":
            self._lan_client.apply_state_all(state)
            return
        light = self._resolve_light(target)
        self._lan_client.apply_state(light.label, state)

    def _resolve_light(self, target: str | None):
        if target is None:
            raise RuntimeError("Action target is required.")
        return self._config.lights[target]

    def _resolve_selector(self, target: str | None) -> str:
        if target is None or target == "all":
            return "all"
        light = self._resolve_light(target)
        return light.selector()

    def _require_http_client(self) -> LifxHttpClient:
        if not self._config.lifx.http.enabled:
            raise LifxHttpError("HTTP transport is not enabled in config.")
        if self._http_client is None:
            self._http_client = LifxHttpClient(
                token_env_var=self._config.lifx.http.token_env_var,
                base_url=self._config.lifx.http.base_url,
            )
        return self._http_client
