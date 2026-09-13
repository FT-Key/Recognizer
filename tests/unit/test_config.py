"""Tests de los modelos de configuracion."""

import pytest
from pydantic import ValidationError

from recognizer.core.config import AppConfig, CameraConfig, HandsConfig
from recognizer.core.constants import (
    DEFAULT_CAMERA_DEVICE_INDEX,
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    DEFAULT_HAND_MODEL_PATH,
    DEFAULT_MAX_HANDS,
    DEFAULT_MIN_DETECTION_CONFIDENCE,
    DEFAULT_MIN_PRESENCE_CONFIDENCE,
    DEFAULT_MIN_TRACKING_CONFIDENCE,
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


def test_hands_defaults() -> None:
    hands = HandsConfig()
    assert hands.model_path == DEFAULT_HAND_MODEL_PATH
    assert hands.max_hands == DEFAULT_MAX_HANDS
    assert hands.min_detection_confidence == DEFAULT_MIN_DETECTION_CONFIDENCE
    assert hands.min_presence_confidence == DEFAULT_MIN_PRESENCE_CONFIDENCE
    assert hands.min_tracking_confidence == DEFAULT_MIN_TRACKING_CONFIDENCE


def test_app_config_uses_hands_defaults() -> None:
    assert AppConfig().hands == HandsConfig()


def test_hands_rejects_zero_max_hands() -> None:
    with pytest.raises(ValidationError):
        HandsConfig.model_validate({"max_hands": 0})


@pytest.mark.parametrize(
    "field",
    ["min_detection_confidence", "min_presence_confidence", "min_tracking_confidence"],
)
@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_hands_rejects_confidence_out_of_range(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        HandsConfig.model_validate({field: value})


def test_hands_rejects_empty_model_path() -> None:
    with pytest.raises(ValidationError):
        HandsConfig.model_validate({"model_path": ""})
