from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from jdi_voice.config import WakeWordConfig
from jdi_voice.wakeword import OpenWakeWordGate, WakeWordError


class _FakeModel:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.models = {"hey jarvis": object()}

    def predict(self, *args, **kwargs):
        return {"hey jarvis": 0.0}

    def reset(self) -> None:
        return None


def test_openwakeword_gate_downloads_builtin_assets(monkeypatch, tmp_path) -> None:
    downloads: list[str] = []

    package_dir = tmp_path / "openwakeword"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")

    fake_openwakeword = types.ModuleType("openwakeword")
    fake_openwakeword.__file__ = str(package_dir / "__init__.py")
    fake_openwakeword.FEATURE_MODELS = {
        "embedding": {"download_url": "https://example.test/embedding_model.tflite"},
        "melspectrogram": {
            "download_url": "https://example.test/melspectrogram.tflite"
        },
    }
    fake_openwakeword.VAD_MODELS = {
        "silero_vad": {"download_url": "https://example.test/silero_vad.onnx"}
    }
    fake_openwakeword.MODELS = {
        "hey_jarvis": {"download_url": "https://example.test/hey_jarvis_v0.1.tflite"}
    }

    fake_model_module = types.ModuleType("openwakeword.model")
    fake_model_module.Model = _FakeModel

    def fake_download_file(url: str, target_directory: str) -> None:
        downloads.append(url)
        target_path = tmp_path / target_directory.split(str(tmp_path))[-1].lstrip("/")
        target_path.mkdir(parents=True, exist_ok=True)
        (target_path / url.rsplit("/", 1)[-1]).write_bytes(b"model")

    fake_utils_module = types.ModuleType("openwakeword.utils")
    fake_utils_module.download_file = fake_download_file

    monkeypatch.setitem(sys.modules, "openwakeword", fake_openwakeword)
    monkeypatch.setitem(sys.modules, "openwakeword.model", fake_model_module)
    monkeypatch.setitem(sys.modules, "openwakeword.utils", fake_utils_module)

    gate = OpenWakeWordGate(
        WakeWordConfig(enabled=True, model_names=("hey jarvis",), inference_framework="onnx")
    )

    assert isinstance(gate, OpenWakeWordGate)
    assert "https://example.test/embedding_model.tflite" in downloads
    assert "https://example.test/embedding_model.onnx" in downloads
    assert "https://example.test/melspectrogram.tflite" in downloads
    assert "https://example.test/melspectrogram.onnx" in downloads
    assert "https://example.test/silero_vad.onnx" in downloads
    assert "https://example.test/hey_jarvis_v0.1.tflite" in downloads
    assert "https://example.test/hey_jarvis_v0.1.onnx" in downloads


def test_openwakeword_gate_uses_debounce_without_patience_for_default_config(
    monkeypatch, tmp_path
) -> None:
    package_dir = tmp_path / "openwakeword"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")

    fake_openwakeword = types.ModuleType("openwakeword")
    fake_openwakeword.__file__ = str(package_dir / "__init__.py")
    fake_openwakeword.FEATURE_MODELS = {}
    fake_openwakeword.VAD_MODELS = {}
    fake_openwakeword.MODELS = {
        "hey_jarvis": {"download_url": "https://example.test/hey_jarvis_v0.1.tflite"}
    }

    captured_kwargs: dict[str, object] = {}

    class PredictRecordingModel(_FakeModel):
        def predict(self, *args, **kwargs):
            captured_kwargs.update(kwargs)
            return {"hey jarvis": 0.0}

    fake_model_module = types.ModuleType("openwakeword.model")
    fake_model_module.Model = PredictRecordingModel

    def fake_download_file(url: str, target_directory: str) -> None:
        target_path = Path(target_directory)
        target_path.mkdir(parents=True, exist_ok=True)
        (target_path / url.rsplit("/", 1)[-1]).write_bytes(b"model")

    fake_utils_module = types.ModuleType("openwakeword.utils")
    fake_utils_module.download_file = fake_download_file

    monkeypatch.setitem(sys.modules, "openwakeword", fake_openwakeword)
    monkeypatch.setitem(sys.modules, "openwakeword.model", fake_model_module)
    monkeypatch.setitem(sys.modules, "openwakeword.utils", fake_utils_module)

    gate = OpenWakeWordGate(
        WakeWordConfig(
            enabled=True,
            model_names=("hey jarvis",),
            patience_frames=1,
            debounce_seconds=1.2,
        )
    )

    gate.process_audio(b"\x00\x00" * 1280)

    assert captured_kwargs["threshold"] == {"hey jarvis": 0.5}
    assert captured_kwargs["debounce_time"] == 1.2
    assert "patience" not in captured_kwargs


def test_openwakeword_gate_rejects_unknown_builtin_model(monkeypatch, tmp_path) -> None:
    package_dir = tmp_path / "openwakeword"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")

    fake_openwakeword = types.ModuleType("openwakeword")
    fake_openwakeword.__file__ = str(package_dir / "__init__.py")
    fake_openwakeword.FEATURE_MODELS = {}
    fake_openwakeword.VAD_MODELS = {}
    fake_openwakeword.MODELS = {
        "hey_jarvis": {"download_url": "https://example.test/hey_jarvis_v0.1.tflite"}
    }

    fake_model_module = types.ModuleType("openwakeword.model")
    fake_model_module.Model = _FakeModel

    fake_utils_module = types.ModuleType("openwakeword.utils")
    fake_utils_module.download_file = lambda url, target_directory: None

    monkeypatch.setitem(sys.modules, "openwakeword", fake_openwakeword)
    monkeypatch.setitem(sys.modules, "openwakeword.model", fake_model_module)
    monkeypatch.setitem(sys.modules, "openwakeword.utils", fake_utils_module)

    with pytest.raises(WakeWordError, match="Unknown openWakeWord model names"):
        OpenWakeWordGate(
            WakeWordConfig(enabled=True, model_names=("definitely not real",))
        )
