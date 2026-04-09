from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .audio import AudioDeviceError, MicrophoneAudioSource
from .config import ConfigError, load_config
from .controller import CommandDispatcher
from .lifx.http_client import LifxHttpError
from .lifx.lan_client import LifxLanError
from .logging_config import configure_logging
from .phrase_matcher import ExactPhraseMatcher
from .push_to_talk import PushToTalkError
from .recognition import RecognitionError
from .service import VoiceAutomationService
from .wakeword import WakeWordError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline Raspberry Pi voice control for LIFX")
    parser.add_argument(
        "--config",
        default="configs/example.yaml",
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run", help="Run the microphone recognition loop.")
    subparsers.add_parser("validate-config", help="Parse and validate the YAML config.")
    subparsers.add_parser("list-audio-devices", help="Show input devices from sounddevice.")

    list_lights = subparsers.add_parser("list-lights", help="List discovered LIFX lights.")
    list_lights.add_argument(
        "--transport",
        choices=("lan", "http"),
        default="lan",
        help="Which LIFX transport to inspect.",
    )

    subparsers.add_parser("list-scenes", help="List scenes from the LIFX HTTP API.")

    dispatch = subparsers.add_parser(
        "dispatch",
        help="Match a phrase from config and execute its action immediately.",
    )
    dispatch.add_argument("phrase", help="Phrase to normalize and dispatch.")

    verifier = subparsers.add_parser(
        "train-wakeword-verifier",
        help="Train an openWakeWord custom verifier model from local audio clips.",
    )
    verifier.add_argument(
        "--model-name",
        required=True,
        help="Base openWakeWord model name, such as `hey_jarvis.onnx`.",
    )
    verifier.add_argument(
        "--positive",
        nargs="+",
        required=True,
        help="Positive reference clips that contain the wake word in your voice.",
    )
    verifier.add_argument(
        "--negative",
        nargs="+",
        required=True,
        help="Negative reference clips with your voice or room audio but no wake word.",
    )
    verifier.add_argument(
        "--output",
        required=True,
        help="Output `.pkl` file for the verifier model.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)

    try:
        if args.command == "list-audio-devices":
            _print_audio_devices()
            return 0

        if args.command == "train-wakeword-verifier":
            _train_wakeword_verifier(
                model_name=args.model_name,
                positive=args.positive,
                negative=args.negative,
                output=args.output,
            )
            return 0

        config = load_config(args.config)

        if args.command == "validate-config":
            print(f"Config is valid: {config.config_path}")
            return 0

        dispatcher = CommandDispatcher(config)

        if args.command == "list-lights":
            for line in dispatcher.list_lights(args.transport):
                print(line)
            return 0

        if args.command == "list-scenes":
            for line in dispatcher.list_http_scenes():
                print(line)
            return 0

        if args.command == "dispatch":
            matcher = ExactPhraseMatcher(config.commands)
            match = matcher.match(args.phrase)
            if match is None:
                print(f"No command matched: {args.phrase}", file=sys.stderr)
                return 1
            result = dispatcher.dispatch(match.command)
            print(result.details)
            return 0

        if args.command == "run":
            VoiceAutomationService(config).run()
            return 0

        parser.error(f"Unhandled command: {args.command}")
        return 2
    except (
        AudioDeviceError,
        ConfigError,
        LifxHttpError,
        LifxLanError,
        PushToTalkError,
        RecognitionError,
        WakeWordError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


def _print_audio_devices() -> None:
    for index, device in enumerate(MicrophoneAudioSource.list_devices()):
        print(f"[{index}] {device}")


def _train_wakeword_verifier(
    model_name: str,
    positive: list[str],
    negative: list[str],
    output: str,
) -> None:
    try:
        import openwakeword
    except ImportError as exc:
        raise WakeWordError(
            "openWakeWord is not installed. Install the optional wake word dependencies first."
        ) from exc

    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    openwakeword.train_custom_verifier(
        positive_reference_clips=positive,
        negative_reference_clips=negative,
        output_path=str(output_path),
        model_name=model_name,
    )
    print(f"Wrote verifier model to {output_path}")


if __name__ == "__main__":
    raise SystemExit(main())
