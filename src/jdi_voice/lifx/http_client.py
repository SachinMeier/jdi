from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import requests


class LifxHttpError(RuntimeError):
    """Raised when the LIFX HTTP API returns an error."""


class LifxHttpClient:
    """Minimal wrapper over the official LIFX HTTP API."""

    def __init__(
        self,
        token_env_var: str,
        base_url: str = "https://api.lifx.com/v1",
        session: requests.Session | None = None,
    ) -> None:
        token = os.getenv(token_env_var)
        if not token:
            raise LifxHttpError(
                f"Environment variable `{token_env_var}` is not set."
            )
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
        )

    def list_lights(self, selector: str = "all") -> list[dict[str, Any]]:
        return self._request_json(
            "GET",
            f"/lights/{self._quote_selector(selector)}",
        )

    def list_scenes(self) -> list[dict[str, Any]]:
        return self._request_json("GET", "/scenes")

    def set_power(
        self,
        selector: str,
        power: str,
        duration_seconds: float = 0.5,
    ) -> list[dict[str, Any]]:
        payload = {
            "power": power,
            "duration": duration_seconds,
        }
        return self._request_json(
            "PUT",
            f"/lights/{self._quote_selector(selector)}/state",
            json=payload,
        )

    def activate_scene(
        self,
        scene_id: str,
        duration_seconds: float = 0.5,
    ) -> list[dict[str, Any]]:
        return self._request_json(
            "PUT",
            f"/scenes/scene_id:{scene_id}/activate",
            json={"duration": duration_seconds},
        )

    def _request_json(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        response = self._session.request(
            method,
            f"{self._base_url}{path}",
            timeout=10,
            **kwargs,
        )
        if response.status_code >= 400:
            raise LifxHttpError(
                f"LIFX HTTP API request failed with {response.status_code}: {response.text}"
            )
        if not response.content:
            return []
        return response.json()

    @staticmethod
    def _quote_selector(selector: str) -> str:
        return quote(selector, safe=":")

