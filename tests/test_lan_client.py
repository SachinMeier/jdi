from __future__ import annotations

import sys
import types

from jdi_voice.config import LightState
from jdi_voice.lifx.lan_client import LifxLanClient


class _FakeDevice:
    def __init__(
        self,
        label: str,
        mac_addr: str,
        ip_addr: str,
        *,
        is_switch: bool = False,
        service: int = 1,
        port: int = 56700,
        source_id: int = 1234,
    ) -> None:
        self.label = label
        self.mac_addr = mac_addr
        self.ip_addr = ip_addr
        self.service = service
        self.port = port
        self.source_id = source_id
        self._is_switch = is_switch

    def get_label(self) -> str:
        return self.label

    def is_switch(self) -> bool:
        return self._is_switch


class _FakeLight:
    instances: list["_FakeLight"] = []

    def __init__(
        self,
        mac_addr: str,
        ip_addr: str,
        service: int = 1,
        port: int = 56700,
        source_id: int = 0,
        verbose: bool = False,
    ) -> None:
        self.mac_addr = mac_addr
        self.ip_addr = ip_addr
        self.service = service
        self.port = port
        self.source_id = source_id
        self.verbose = verbose
        self.label = ""
        self.power_calls: list[tuple[str, int]] = []
        self.color_calls: list[tuple[tuple[int, int, int, int], int]] = []
        _FakeLight.instances.append(self)

    def set_power(self, power: str, duration: int = 0) -> None:
        self.power_calls.append((power, duration))

    def get_color(self) -> tuple[int, int, int, int]:
        return (0, 0, 1000, 3500)

    def set_color(self, color: tuple[int, int, int, int], duration: int = 0) -> None:
        self.color_calls.append((color, duration))


class _FakeLifxLAN:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.source_id = 777
        self.set_power_all_calls: list[tuple[str, int]] = []

    def get_devices(self):
        return [
            _FakeDevice("Bedroom1", "aa:bb", "10.0.0.10"),
            _FakeDevice("Kitchen", "cc:dd", "10.0.0.11"),
            _FakeDevice("Switch", "ee:ff", "10.0.0.12", is_switch=True),
        ]

    def set_power_all_lights(self, power: str, duration: int = 0) -> None:
        self.set_power_all_calls.append((power, duration))


def test_lan_client_discovers_devices_even_when_library_misclassifies_lights(
    monkeypatch,
) -> None:
    fake_lifxlan_module = types.ModuleType("lifxlan")
    fake_lifxlan_module.LifxLAN = _FakeLifxLAN
    fake_light_module = types.ModuleType("lifxlan.light")
    fake_light_module.Light = _FakeLight

    monkeypatch.setitem(sys.modules, "lifxlan", fake_lifxlan_module)
    monkeypatch.setitem(sys.modules, "lifxlan.light", fake_light_module)
    _FakeLight.instances = []

    client = LifxLanClient()

    lights = client.list_lights(force_refresh=True)

    assert lights == [
        type(lights[0])(label="Bedroom1", identifier="aa:bb", transport="lan"),
        type(lights[1])(label="Kitchen", identifier="cc:dd", transport="lan"),
    ]


def test_lan_client_controls_wrapped_unknown_products(monkeypatch) -> None:
    fake_lifxlan_module = types.ModuleType("lifxlan")
    fake_lifxlan_module.LifxLAN = _FakeLifxLAN
    fake_light_module = types.ModuleType("lifxlan.light")
    fake_light_module.Light = _FakeLight

    monkeypatch.setitem(sys.modules, "lifxlan", fake_lifxlan_module)
    monkeypatch.setitem(sys.modules, "lifxlan.light", fake_light_module)
    _FakeLight.instances = []

    client = LifxLanClient()

    client.set_power("Bedroom1", "on", duration_seconds=0.4)
    client.apply_state(
        "Kitchen",
        LightState(power="on", brightness_pct=10, duration_seconds=0.3),
    )

    bedroom = next(light for light in _FakeLight.instances if light.label == "Bedroom1")
    kitchen = next(light for light in _FakeLight.instances if light.label == "Kitchen")

    assert bedroom.power_calls == [("on", 400)]
    assert kitchen.power_calls == [("on", 300)]
    assert kitchen.color_calls
