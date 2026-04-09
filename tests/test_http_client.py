from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jdi_voice.lifx.http_client import LifxHttpClient


@dataclass
class _FakeResponse:
    status_code: int
    payload: Any

    @property
    def content(self) -> bytes:
        return b"{}"

    @property
    def text(self) -> str:
        return str(self.payload)

    def json(self) -> Any:
        return self.payload


class _FakeSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, timeout: int, **kwargs: Any) -> _FakeResponse:
        self.calls.append((method, url, kwargs))
        return _FakeResponse(status_code=200, payload=[{"ok": True}])


def test_http_client_quotes_selector_and_sets_authorization(monkeypatch) -> None:
    monkeypatch.setenv("LIFX_TOKEN", "secret-token")
    session = _FakeSession()
    client = LifxHttpClient(token_env_var="LIFX_TOKEN", session=session)

    client.set_power("label:Bedroom Main", "on", duration_seconds=0.75)

    assert session.headers["Authorization"] == "Bearer secret-token"
    method, url, kwargs = session.calls[0]
    assert method == "PUT"
    assert url.endswith("/lights/label:Bedroom%20Main/state")
    assert kwargs["json"] == {"power": "on", "duration": 0.75}


def test_http_client_uses_scene_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("LIFX_TOKEN", "secret-token")
    session = _FakeSession()
    client = LifxHttpClient(token_env_var="LIFX_TOKEN", session=session)

    client.activate_scene("abc-123", duration_seconds=1.2)

    method, url, kwargs = session.calls[0]
    assert method == "PUT"
    assert url.endswith("/scenes/scene_id:abc-123/activate")
    assert kwargs["json"] == {"duration": 1.2}

