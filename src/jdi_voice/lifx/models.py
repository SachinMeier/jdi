from __future__ import annotations

from dataclasses import dataclass

from ..config import LightState


@dataclass(frozen=True)
class DiscoveredLight:
    label: str
    identifier: str
    transport: str


def brightness_pct_to_u16(value: float) -> int:
    return max(0, min(65_535, round(value / 100 * 65_535)))


def saturation_pct_to_u16(value: float) -> int:
    return max(0, min(65_535, round(value / 100 * 65_535)))


def hue_deg_to_u16(value: float) -> int:
    return max(0, min(65_535, round((value % 360) / 360 * 65_535)))


def merge_light_state(existing_hsbk: tuple[int, int, int, int], state: LightState) -> tuple[int, int, int, int]:
    hue, saturation, brightness, kelvin = existing_hsbk
    if state.hue_deg is not None:
        hue = hue_deg_to_u16(state.hue_deg)
    if state.saturation_pct is not None:
        saturation = saturation_pct_to_u16(state.saturation_pct)
    if state.brightness_pct is not None:
        brightness = brightness_pct_to_u16(state.brightness_pct)
    if state.kelvin is not None:
        kelvin = state.kelvin
    return (hue, saturation, brightness, kelvin)

