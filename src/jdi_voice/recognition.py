from __future__ import annotations

import json
from pathlib import Path


class RecognitionError(RuntimeError):
    """Raised when Vosk recognition cannot start."""


class VoskSession:
    def __init__(self, recognizer) -> None:
        self._recognizer = recognizer

    def accept_audio(self, audio_bytes: bytes) -> str | None:
        if self._recognizer.AcceptWaveform(audio_bytes):
            result = json.loads(self._recognizer.Result())
            text = str(result.get("text", "")).strip()
            return text or None
        return None

    def finalize(self) -> str | None:
        result = json.loads(self._recognizer.FinalResult())
        text = str(result.get("text", "")).strip()
        return text or None


class VoskPhraseRecognizer:
    """Creates grammar-constrained Vosk recognizers for narrow command sets."""

    def __init__(
        self,
        model_path: Path,
        sample_rate_hz: int,
        allowed_phrases: tuple[str, ...],
        allow_unknown: bool = True,
    ) -> None:
        try:
            from vosk import Model
        except ImportError as exc:
            raise RecognitionError(
                "vosk is not installed. Install project dependencies first."
            ) from exc

        if not model_path.exists():
            raise RecognitionError(f"Vosk model path does not exist: {model_path}")

        self._sample_rate_hz = sample_rate_hz
        self._allowed_phrases = list(allowed_phrases)
        if allow_unknown:
            self._allowed_phrases.append("[unk]")
        self._model = Model(str(model_path))

    def new_session(self) -> VoskSession:
        try:
            from vosk import KaldiRecognizer
        except ImportError as exc:
            raise RecognitionError(
                "vosk is not installed. Install project dependencies first."
            ) from exc

        recognizer = KaldiRecognizer(
            self._model,
            self._sample_rate_hz,
            json.dumps(self._allowed_phrases),
        )
        recognizer.SetWords(False)
        recognizer.SetPartialWords(False)
        return VoskSession(recognizer)

