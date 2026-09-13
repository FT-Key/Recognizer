"""Tests de la carga de configuracion YAML."""

from pathlib import Path

import pytest

from recognizer.core.constants import DEFAULT_CAMERA_DEVICE_INDEX
from recognizer.core.errors import ConfigError
from recognizer.settings import load_config

VALID_YAML = """
camera:
  device_index: 1
  width: 320
  height: 240
  target_fps: 15
"""


def _write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_valid_config(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path, VALID_YAML))
    assert config.camera.device_index == 1
    assert config.camera.width == 320
    assert config.camera.height == 240
    assert config.camera.target_fps == 15


def test_empty_file_uses_defaults(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path, ""))
    assert config.camera.device_index == DEFAULT_CAMERA_DEVICE_INDEX


def test_missing_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "no-existe.yaml")


def test_invalid_yaml_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(_write_config(tmp_path, "camera: ["))


def test_non_mapping_root_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(_write_config(tmp_path, "- item"))


def test_invalid_values_raise_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(_write_config(tmp_path, VALID_YAML.replace("width: 320", "width: -5")))
