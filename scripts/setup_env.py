#!/usr/bin/env python3
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
VOSK_MODEL_NAME = "vosk-model-small-en-us-0.15"
VOSK_MODEL_URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"
OPENWAKEWORD_VERSION = "0.6.0"


def _run(command: list[str]) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def _platform_name() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Linux":
        return "linux"
    raise RuntimeError(f"Unsupported platform for bootstrap: {system}")


def _default_config_path(platform_name: str) -> Path:
    if platform_name == "macos":
        return REPO_ROOT / "configs" / "mac-test.yaml"
    return REPO_ROOT / "configs" / "home.yaml"


def _resolve_config_path(raw_path: str | None, platform_name: str) -> Path:
    if raw_path is None:
        return _default_config_path(platform_name)

    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def _ensure_config(config_path: Path) -> None:
    if config_path.exists():
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO_ROOT / "configs" / "example.yaml", config_path)
    print(f"Created config from example: {config_path}")


def _install_python_dependencies(*, with_dev: bool, with_wakeword: bool) -> None:
    python = sys.executable
    _run([python, "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools"])
    requirements_file = "requirements-dev.txt" if with_dev else "requirements.txt"
    _run([python, "-m", "pip", "install", "-r", requirements_file])
    _run([python, "-m", "pip", "install", "-e", "."])

    if not with_wakeword:
        return

    platform_name = _platform_name()
    wakeword_requirements = (
        "requirements-wakeword.txt"
        if platform_name == "macos"
        else "requirements-wakeword-linux.txt"
    )
    _run([python, "-m", "pip", "install", "-r", wakeword_requirements])
    if platform_name == "linux":
        _run(
            [
                python,
                "-m",
                "pip",
                "install",
                "--no-deps",
                f"openwakeword=={OPENWAKEWORD_VERSION}",
            ]
        )


def _download_vosk_model() -> Path:
    models_dir = REPO_ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_dir = models_dir / VOSK_MODEL_NAME
    if model_dir.exists():
        print(f"Vosk model already present: {model_dir}")
        return model_dir

    print(f"Downloading Vosk model from {VOSK_MODEL_URL}")
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_handle:
        temp_zip_path = Path(temp_handle.name)

    try:
        with urlopen(VOSK_MODEL_URL) as response, temp_zip_path.open("wb") as output:
            shutil.copyfileobj(response, output)
        with zipfile.ZipFile(temp_zip_path) as archive:
            archive.extractall(models_dir)
    finally:
        temp_zip_path.unlink(missing_ok=True)

    return model_dir


def _validate_runtime(config_path: Path, *, with_wakeword: bool) -> None:
    sys.path.insert(0, str(REPO_ROOT / "src"))

    from jdi_voice.config import load_config

    config = load_config(config_path)
    print(f"Validated config: {config_path}")

    if with_wakeword and config.wake_word.enabled:
        from jdi_voice.wakeword import OpenWakeWordGate

        gate = OpenWakeWordGate(config.wake_word)
        gate.reset()
        print("Wake word runtime check passed.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap the local JDI environment in one command."
    )
    parser.add_argument(
        "--with-dev",
        action="store_true",
        help="Install development dependencies in addition to runtime dependencies.",
    )
    parser.add_argument(
        "--with-wakeword",
        action="store_true",
        help="Install the optional wake-word dependencies and verify wake-word startup.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Config file to create if missing and validate after setup.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    platform_name = _platform_name()
    config_path = _resolve_config_path(args.config, platform_name)

    _ensure_config(config_path)
    _install_python_dependencies(
        with_dev=args.with_dev,
        with_wakeword=args.with_wakeword,
    )
    _download_vosk_model()
    _validate_runtime(config_path, with_wakeword=args.with_wakeword)

    print("\nSetup complete.")
    print(f"Config file: {config_path}")
    if args.with_wakeword:
        print(f"Wake word can now be tested with: jdi --config {config_path} run")
    else:
        print(f"Voice loop can now be tested with: jdi --config {config_path} run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
