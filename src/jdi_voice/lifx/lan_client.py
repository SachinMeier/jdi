from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ..config import LightState
from .models import DiscoveredLight, merge_light_state


class LifxLanError(RuntimeError):
    """Raised when local LIFX LAN control fails."""


@dataclass
class _CachedDiscovery:
    lights: list[Any]
    refreshed_at: float


class LifxLanClient:
    """Thin wrapper around the `lifxlan` library for local control."""

    def __init__(
        self,
        discovery_cache_seconds: float = 30.0,
        verbose: bool = False,
    ) -> None:
        self._discovery_cache_seconds = discovery_cache_seconds
        self._verbose = verbose
        self._cache: _CachedDiscovery | None = None

        try:
            from lifxlan import LifxLAN
            from lifxlan.light import Light
        except ImportError as exc:
            raise LifxLanError(
                "lifxlan is not installed. Install project dependencies first."
            ) from exc

        self._client = LifxLAN(verbose=verbose)
        self._light_class = Light

    def list_lights(self, force_refresh: bool = False) -> list[DiscoveredLight]:
        lights = self._get_lights(force_refresh=force_refresh)
        discovered: list[DiscoveredLight] = []
        for light in lights:
            discovered.append(
                DiscoveredLight(
                    label=self._get_cached_label(light),
                    identifier=getattr(light, "mac_addr", None)
                    or self._get_cached_label(light),
                    transport="lan",
                )
            )
        return discovered

    def set_power(
        self,
        label: str,
        power: str,
        duration_seconds: float = 0.5,
    ) -> None:
        light = self._get_light(label)
        light.set_power(power, duration=int(duration_seconds * 1000))

    def set_power_all(self, power: str, duration_seconds: float = 0.5) -> None:
        self._client.set_power_all_lights(power, duration=int(duration_seconds * 1000))

    def apply_state(self, label: str, state: LightState) -> None:
        light = self._get_light(label)
        self._apply_state_to_light(light, state)

    def apply_state_all(self, state: LightState) -> None:
        for light in self._get_lights(force_refresh=False):
            self._apply_state_to_light(light, state)

    def _apply_state_to_light(self, light: Any, state: LightState) -> None:
        duration_ms = int(state.duration_seconds * 1000)
        if state.power == "on":
            light.set_power("on", duration=duration_ms)
        if state.has_color_change():
            current_hsbk = tuple(light.get_color())
            next_hsbk = merge_light_state(current_hsbk, state)
            light.set_color(next_hsbk, duration=duration_ms)
        if state.power == "off":
            light.set_power("off", duration=duration_ms)

    def _get_light(self, label: str) -> Any:
        for light in self._get_lights(force_refresh=False):
            if self._get_cached_label(light) == label:
                return light
        for light in self._get_lights(force_refresh=True):
            if self._get_cached_label(light) == label:
                return light
        raise LifxLanError(f"Unable to find LIFX light with label `{label}`.")

    def _get_lights(self, force_refresh: bool) -> list[Any]:
        if force_refresh or self._cache is None or self._cache_expired():
            try:
                lights = list(self._discover_light_like_devices())
            except Exception as exc:  # pragma: no cover - hardware/network dependent
                raise LifxLanError(f"LIFX LAN discovery failed: {exc}") from exc
            self._cache = _CachedDiscovery(lights=lights, refreshed_at=time.monotonic())
        return self._cache.lights

    def _discover_light_like_devices(self) -> list[Any]:
        devices = list(self._client.get_devices())
        lights: list[Any] = []
        for device in devices:
            if self._is_switch(device):
                continue
            wrapped = self._light_class(
                getattr(device, "mac_addr"),
                getattr(device, "ip_addr"),
                getattr(device, "service", 1),
                getattr(device, "port", 56700),
                getattr(device, "source_id", self._client.source_id),
                self._verbose,
            )
            label = getattr(device, "label", None)
            if label is None:
                label = device.get_label()
            setattr(wrapped, "label", label)
            lights.append(wrapped)
        return lights

    @staticmethod
    def _get_cached_label(light: Any) -> str:
        label = getattr(light, "label", None)
        if label is not None:
            return label
        return light.get_label()

    @staticmethod
    def _is_switch(device: Any) -> bool:
        try:
            return bool(device.is_switch())
        except Exception:
            return False

    def _cache_expired(self) -> bool:
        if self._cache is None:
            return True
        return (time.monotonic() - self._cache.refreshed_at) > self._discovery_cache_seconds
