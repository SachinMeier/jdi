from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import WakeWordConfig


class WakeWordError(RuntimeError):
    """Raised when openWakeWord cannot be initialized."""


@dataclass(frozen=True)
class WakeWordDetection:
    model_name: str
    score: float


def _normalize_builtin_model_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def _ensure_openwakeword_assets(config: WakeWordConfig) -> None:
    try:
        import openwakeword
        from openwakeword.utils import download_file
    except ImportError as exc:
        raise WakeWordError(
            "openWakeWord is not installed. Install the optional wake word dependencies."
        ) from exc

    resources_dir = (
        Path(openwakeword.__file__).resolve().parent / "resources" / "models"
    )
    resources_dir.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    for model in openwakeword.FEATURE_MODELS.values():
        urls.append(model["download_url"])
        urls.append(model["download_url"].replace(".tflite", ".onnx"))
    for model in openwakeword.VAD_MODELS.values():
        urls.append(model["download_url"])

    if not config.model_paths:
        normalized_names = [
            _normalize_builtin_model_name(name) for name in config.model_names
        ]
        selected_models = [
            metadata
            for model_name, metadata in openwakeword.MODELS.items()
            if not normalized_names or model_name in normalized_names
        ]
        if normalized_names and not selected_models:
            formatted_names = ", ".join(sorted(normalized_names))
            raise WakeWordError(
                f"Unknown openWakeWord model names: {formatted_names}."
            )
        for model in selected_models:
            urls.append(model["download_url"])
            urls.append(model["download_url"].replace(".tflite", ".onnx"))

    for url in dict.fromkeys(urls):
        filename = url.rsplit("/", 1)[-1]
        if (resources_dir / filename).exists():
            continue
        try:
            download_file(url, str(resources_dir))
        except Exception as exc:  # pragma: no cover - network failure path
            raise WakeWordError(
                f"Unable to download openWakeWord model asset `{filename}`."
            ) from exc


class OpenWakeWordGate:
    """Optional wake word detector that wraps openWakeWord."""

    def __init__(self, config: WakeWordConfig) -> None:
        self._config = config

        try:
            from openwakeword.model import Model
        except ImportError as exc:
            raise WakeWordError(
                "openWakeWord is not installed. Install the optional wake word dependencies."
            ) from exc

        _ensure_openwakeword_assets(config)
        wakeword_models = list(config.model_paths) or list(config.model_names)
        self._model = Model(
            wakeword_models=wakeword_models,
            enable_speex_noise_suppression=config.enable_speex_noise_suppression,
            vad_threshold=config.vad_threshold,
            custom_verifier_models=config.custom_verifier_models,
            custom_verifier_threshold=config.custom_verifier_threshold,
            inference_framework=config.inference_framework,
        )
        self._thresholds = {
            name: config.threshold for name in self._model.models.keys()
        }
        self._patience = (
            {name: config.patience_frames for name in self._model.models.keys()}
            if config.patience_frames > 1
            else {}
        )

    def process_audio(self, audio_bytes: bytes) -> WakeWordDetection | None:
        try:
            import numpy as np
        except ImportError as exc:
            raise WakeWordError("numpy is required for wake word inference.") from exc

        frame = np.frombuffer(audio_bytes, dtype=np.int16)
        predict_kwargs = {"threshold": self._thresholds}
        if self._patience:
            predict_kwargs["patience"] = self._patience
        elif self._config.debounce_seconds > 0:
            predict_kwargs["debounce_time"] = self._config.debounce_seconds

        predictions = self._model.predict(frame, **predict_kwargs)
        active_scores = {
            name: score
            for name, score in predictions.items()
            if score >= self._config.threshold
        }
        if not active_scores:
            return None
        model_name, score = max(active_scores.items(), key=lambda item: item[1])
        return WakeWordDetection(model_name=model_name, score=float(score))

    def reset(self) -> None:
        self._model.reset()
