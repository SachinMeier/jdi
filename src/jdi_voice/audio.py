from __future__ import annotations

import queue
from typing import Any


class AudioDeviceError(RuntimeError):
    """Raised when microphone access fails."""


class MicrophoneAudioSource:
    """Streams 16-bit PCM audio from the default or configured microphone."""

    def __init__(
        self,
        sample_rate_hz: int,
        block_size_frames: int,
        channels: int = 1,
        device: str | int | None = None,
    ) -> None:
        self._sample_rate_hz = sample_rate_hz
        self._block_size_frames = block_size_frames
        self._channels = channels
        self._device = device
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._stream: Any | None = None
        self._status_error: str | None = None

    def __enter__(self) -> "MicrophoneAudioSource":
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioDeviceError(
                "sounddevice is not installed. Install project dependencies first."
            ) from exc

        def callback(indata: Any, frames: int, time: Any, status: Any) -> None:
            if status:
                self._status_error = str(status)
            self._queue.put(bytes(indata))

        try:
            self._stream = sd.RawInputStream(
                samplerate=self._sample_rate_hz,
                blocksize=self._block_size_frames,
                device=self._device,
                dtype="int16",
                channels=self._channels,
                callback=callback,
            )
            self._stream.start()
        except Exception as exc:
            raise AudioDeviceError(f"Unable to open microphone stream: {exc}") from exc
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def read(self, timeout_seconds: float = 1.0) -> bytes:
        if self._status_error is not None:
            raise AudioDeviceError(self._status_error)
        try:
            return self._queue.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise AudioDeviceError("Timed out waiting for microphone audio.") from exc

    @staticmethod
    def list_devices() -> list[dict[str, Any]]:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioDeviceError(
                "sounddevice is not installed. Install project dependencies first."
            ) from exc
        return list(sd.query_devices())
