from __future__ import annotations

import builtins
import textwrap
from pathlib import Path

from jdi_voice.cli import main
from jdi_voice.lifx.http_client import LifxHttpError


def _write_config(tmp_path: Path, body: str) -> Path:
    config_path = tmp_path / "home.yaml"
    config_path.write_text(textwrap.dedent(body).strip(), encoding="utf-8")
    return config_path


def test_train_wakeword_verifier_reports_clean_error(monkeypatch, capsys) -> None:
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openwakeword":
            raise ImportError("missing optional dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    exit_code = main(
        [
            "train-wakeword-verifier",
            "--model-name",
            "hey_jarvis.onnx",
            "--positive",
            "positive.wav",
            "--negative",
            "negative.wav",
            "--output",
            "runtime/verifier.pkl",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error: openWakeWord is not installed." in captured.err
    assert "Traceback" not in captured.err


def test_list_scenes_prints_http_results(monkeypatch, tmp_path: Path, capsys) -> None:
    class FakeLanClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeHttpClient:
        def __init__(self, token_env_var: str, base_url: str) -> None:
            self.token_env_var = token_env_var
            self.base_url = base_url

        def list_scenes(self):
            return [{"name": "Movie Time", "uuid": "scene-1"}]

    config_path = _write_config(
        tmp_path,
        """
        recognition:
          model_path: /unused/in-test
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
        """,
    )

    monkeypatch.setenv("LIFX_TOKEN", "secret-token")
    monkeypatch.setattr("jdi_voice.controller.LifxLanClient", FakeLanClient)
    monkeypatch.setattr("jdi_voice.controller.LifxHttpClient", FakeHttpClient)

    exit_code = main(["--config", str(config_path), "list-scenes"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "Movie Time (scene-1)"


def test_list_lights_http_reports_missing_token_cleanly(monkeypatch, tmp_path: Path, capsys) -> None:
    config_path = _write_config(
        tmp_path,
        """
        recognition:
          model_path: /unused/in-test
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
        """,
    )

    monkeypatch.delenv("LIFX_TOKEN", raising=False)

    exit_code = main(["--config", str(config_path), "list-lights", "--transport", "http"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Environment variable `LIFX_TOKEN` is not set." in captured.err
    assert "Traceback" not in captured.err


def test_list_scenes_reports_http_api_errors_cleanly(monkeypatch, tmp_path: Path, capsys) -> None:
    class FakeLanClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FailingHttpClient:
        def __init__(self, token_env_var: str, base_url: str) -> None:
            self.token_env_var = token_env_var
            self.base_url = base_url

        def list_scenes(self):
            raise LifxHttpError("simulated HTTP failure")

    config_path = _write_config(
        tmp_path,
        """
        recognition:
          model_path: /unused/in-test
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
        """,
    )

    monkeypatch.setenv("LIFX_TOKEN", "secret-token")
    monkeypatch.setattr("jdi_voice.controller.LifxLanClient", FakeLanClient)
    monkeypatch.setattr("jdi_voice.controller.LifxHttpClient", FailingHttpClient)

    exit_code = main(["--config", str(config_path), "list-scenes"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error: simulated HTTP failure" in captured.err
    assert "Traceback" not in captured.err
