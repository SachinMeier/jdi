from __future__ import annotations

import logging
import math
import time

from .audio import AudioDeviceError, MicrophoneAudioSource
from .config import AppConfig
from .controller import CommandDispatcher
from .phrase_matcher import ExactPhraseMatcher
from .push_to_talk import GpioPushToTalkButton, TerminalKeyTrigger
from .recognition import VoskPhraseRecognizer
from .wakeword import OpenWakeWordGate


class VoiceAutomationService:
    """Coordinates microphone capture, recognition, phrase matching, and dispatch."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._logger = logging.getLogger(__name__)
        self._matcher = ExactPhraseMatcher(config.commands)
        self._recognizer = VoskPhraseRecognizer(
            model_path=config.recognition.model_path,
            sample_rate_hz=config.audio.sample_rate_hz,
            allowed_phrases=self._matcher.phrases,
            allow_unknown=config.recognition.allow_unknown,
        )
        self._dispatcher = CommandDispatcher(config)
        self._wake_word = (
            OpenWakeWordGate(config.wake_word) if config.wake_word.enabled else None
        )
        self._push_to_talk = (
            GpioPushToTalkButton(
                gpio_pin=config.push_to_talk.gpio_pin,
                pull_up=config.push_to_talk.pull_up,
                bounce_time_seconds=config.push_to_talk.bounce_time_seconds,
            )
            if config.push_to_talk.enabled and config.push_to_talk.mode == "gpio"
            else None
        )
        self._keyboard_push_to_talk = (
            TerminalKeyTrigger(config.push_to_talk.keyboard_key)
            if config.push_to_talk.enabled and config.push_to_talk.mode == "keyboard"
            else None
        )

    def run(self) -> None:
        self._logger.info("Starting voice automation loop.")
        with MicrophoneAudioSource(
            sample_rate_hz=self._config.audio.sample_rate_hz,
            block_size_frames=self._config.audio.block_size_frames,
            channels=self._config.audio.channels,
            device=self._config.audio.device,
        ) as microphone:
            if self._keyboard_push_to_talk is not None:
                with self._keyboard_push_to_talk as trigger:
                    self._run_keyboard_push_to_talk(microphone, trigger)
            elif self._push_to_talk is not None:
                self._run_push_to_talk(microphone)
            elif self._wake_word is not None:
                self._run_wake_word(microphone)
            else:
                self._run_always_listening(microphone)

    def _run_always_listening(self, microphone: MicrophoneAudioSource) -> None:
        session = self._recognizer.new_session()
        while True:
            audio = microphone.read()
            transcript = session.accept_audio(audio)
            if transcript is None:
                continue
            self._handle_transcript(transcript)
            session = self._recognizer.new_session()

    def _run_push_to_talk(self, microphone: MicrophoneAudioSource) -> None:
        while True:
            audio = microphone.read()
            if not self._push_to_talk or not self._push_to_talk.is_pressed:
                continue
            self._logger.info("Push-to-talk active. Listening for one command.")
            transcript = self._capture_command(
                microphone=microphone,
                initial_audio=audio,
                until_button_release=True,
            )
            if transcript:
                self._handle_transcript(transcript)

    def _run_keyboard_push_to_talk(
        self,
        microphone: MicrophoneAudioSource,
        trigger: TerminalKeyTrigger,
    ) -> None:
        self._logger.info(
            "Keyboard push-to-talk enabled. Press `%s` in this terminal to arm one command.",
            self._config.push_to_talk.keyboard_key,
        )
        while True:
            trigger.wait_for_press()
            self._logger.info("Keyboard push-to-talk armed. Speak one command.")
            transcript = self._capture_command(microphone=microphone)
            if transcript:
                self._handle_transcript(transcript)

    def _run_wake_word(self, microphone: MicrophoneAudioSource) -> None:
        if self._wake_word is None:
            raise RuntimeError("Wake word mode requested without a wake word detector.")

        discard_chunks = math.ceil(
            self._config.audio.post_wake_delay_seconds
            * self._config.audio.sample_rate_hz
            / self._config.audio.block_size_frames
        )

        while True:
            audio = microphone.read()
            detection = self._wake_word.process_audio(audio)
            if detection is None:
                continue
            self._logger.info(
                "Wake word detected by `%s` (score %.3f).",
                detection.model_name,
                detection.score,
            )
            for _ in range(discard_chunks):
                microphone.read()
            transcript = self._capture_command(microphone=microphone)
            self._wake_word.reset()
            if transcript:
                self._handle_transcript(transcript)

    def _capture_command(
        self,
        microphone: MicrophoneAudioSource,
        initial_audio: bytes | None = None,
        until_button_release: bool = False,
    ) -> str | None:
        session = self._recognizer.new_session()
        deadline = time.monotonic() + self._config.audio.command_timeout_seconds
        audio = initial_audio
        while time.monotonic() < deadline:
            if audio is None:
                audio = microphone.read(timeout_seconds=0.5)
            transcript = session.accept_audio(audio)
            if transcript is not None:
                return transcript
            audio = None
            if until_button_release and self._push_to_talk and not self._push_to_talk.is_pressed:
                break
        return session.finalize()

    def _handle_transcript(self, transcript: str) -> None:
        self._logger.info("Recognized transcript: %s", transcript)
        match = self._matcher.match(transcript)
        if match is None:
            self._logger.warning("No configured command matched `%s`.", transcript)
            return
        result = self._dispatcher.dispatch(match.command)
        self._logger.info("Executed command: %s", result.details)


__all__ = [
    "AudioDeviceError",
    "VoiceAutomationService",
]
