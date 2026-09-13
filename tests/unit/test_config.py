"""Tests de los modelos de configuracion."""

import pytest
from pydantic import ValidationError

from recognizer.core.config import AppConfig, CameraConfig
from recognizer.core.constants import (
    DEFAULT_CAMERA_DEVICE_INDEX,
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    DEFAULT_TARGET_FPS,
)


def test_camera_defaults() -> None:
    camera = CameraConfig()
    assert camera.device_index == DEFAULT_CAMERA_DEVICE_INDEX
    assert camera.width == DEFAULT_FRAME_WIDTH
    assert camera.height == DEFAULT_FRAME_HEIGHT
    assert camera.target_fps == DEFAULT_TARGET_FPS


def test_app_config_uses_camera_defaults() -> None:
    config = AppConfig()
    assert config.camera == CameraConfig()


@pytest.mark.parametrize("field", ["width", "height", "target_fps"])
def test_camera_rejects_non_positive_values(field: str) -> None:
    with pytest.raises(ValidationError):
        CameraConfig.model_validate({field: 0})


def test_camera_rejects_negative_device_index() -> None:
    with pytest.raises(ValidationError):
        CameraConfig.model_validate({"device_index": -1})


def test_unknown_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"camera": {"width": 320}, "unknown": True})
