from jdi_voice.config import LightState
from jdi_voice.lifx.models import merge_light_state


def test_merge_light_state_updates_only_requested_fields() -> None:
    existing = (0, 100, 200, 2500)
    state = LightState(brightness_pct=50, kelvin=3500)

    merged = merge_light_state(existing, state)

    assert merged[0] == 0
    assert merged[1] == 100
    assert merged[2] > 30_000
    assert merged[3] == 3500

