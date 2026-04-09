from __future__ import annotations

import tomllib
from pathlib import Path


def test_systemd_unit_makes_env_file_optional() -> None:
    service_path = Path("systemd/jdi.service")
    contents = service_path.read_text(encoding="utf-8")

    assert "EnvironmentFile=-/etc/jdi.env" in contents


def test_pyproject_includes_gpiozero_dependency() -> None:
    with Path("pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)

    dependencies = pyproject["project"]["dependencies"]
    assert any(dependency.startswith("gpiozero") for dependency in dependencies)


def test_pyproject_exposes_jdi_console_script() -> None:
    with Path("pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)

    assert pyproject["project"]["name"] == "jdi"
    scripts = pyproject["project"]["scripts"]
    assert set(scripts) == {"jdi"}
    assert scripts["jdi"] == "jdi_voice.cli:main"
