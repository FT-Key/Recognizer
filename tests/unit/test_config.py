"""Tests de los modelos de configuracion."""

import pytest
from pydantic import ValidationError

from recognizer.core.config import (
    ActiveZoneConfig,
    AppConfig,
    CameraConfig,
    FaceAuthConfig,
    GestureConfig,
    HandsConfig,
    PointerConfig,
)
from recognizer.core.constants import (
    DEFAULT_CAMERA_DEVICE_INDEX,
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    DEFAULT_GESTURE_MODEL_PATH,
    DEFAULT_HAND_MODEL_PATH,
    DEFAULT_MAX_HANDS,
    DEFAULT_MIN_DETECTION_CONFIDENCE,
    DEFAULT_MIN_GESTURE_CONFIDENCE,
    DEFAULT_MIN_PASSWORD_LENGTH,
    DEFAULT_MIN_PRESENCE_CONFIDENCE,
    DEFAULT_MIN_TRACKING_CONFIDENCE,
    DEFAULT_POINTER_ACTIVE_ZONE_MAX,
    DEFAULT_POINTER_ACTIVE_ZONE_MIN,
    DEFAULT_POINTER_ENABLED,
    DEFAULT_POINTER_MIRROR_X,
    DEFAULT_POINTER_SMOOTHING_ALPHA,
    DEFAULT_RELEASE_FRAMES,
    DEFAULT_STABILIZATION_FRAMES,
    DEFAULT_TARGET_FPS,
)
from recognizer.core.domain.gesture import GESTURE_NONE, GESTURE_POINTING_UP
from recognizer.core.domain.pointer import SmoothingKind


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


def test_gesture_defaults() -> None:
    gestures = GestureConfig()
    assert gestures.model_path == DEFAULT_GESTURE_MODEL_PATH
    assert gestures.max_hands == DEFAULT_MAX_HANDS
    assert gestures.min_detection_confidence == DEFAULT_MIN_DETECTION_CONFIDENCE
    assert gestures.min_presence_confidence == DEFAULT_MIN_PRESENCE_CONFIDENCE
    assert gestures.min_tracking_confidence == DEFAULT_MIN_TRACKING_CONFIDENCE
    assert gestures.stabilization_frames == DEFAULT_STABILIZATION_FRAMES
    assert gestures.release_frames == DEFAULT_RELEASE_FRAMES
    assert gestures.min_gesture_confidence == DEFAULT_MIN_GESTURE_CONFIDENCE


def test_app_config_uses_gesture_defaults() -> None:
    assert AppConfig().gestures == GestureConfig()


@pytest.mark.parametrize("field", ["stabilization_frames", "release_frames"])
def test_gesture_rejects_zero_counters(field: str) -> None:
    with pytest.raises(ValidationError):
        GestureConfig.model_validate({field: 0})


@pytest.mark.parametrize(
    "field",
    [
        "min_detection_confidence",
        "min_presence_confidence",
        "min_tracking_confidence",
        "min_gesture_confidence",
    ],
)
@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_gesture_rejects_confidence_out_of_range(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        GestureConfig.model_validate({field: value})


def test_gesture_rejects_empty_model_path() -> None:
    with pytest.raises(ValidationError):
        GestureConfig.model_validate({"model_path": ""})


def test_active_zone_defaults() -> None:
    zone = ActiveZoneConfig()
    assert zone.x_min == DEFAULT_POINTER_ACTIVE_ZONE_MIN
    assert zone.x_max == DEFAULT_POINTER_ACTIVE_ZONE_MAX
    assert zone.y_min == DEFAULT_POINTER_ACTIVE_ZONE_MIN
    assert zone.y_max == DEFAULT_POINTER_ACTIVE_ZONE_MAX


def test_pointer_defaults() -> None:
    pointer = PointerConfig()
    assert pointer.enabled == DEFAULT_POINTER_ENABLED
    assert pointer.activation_gesture == GESTURE_POINTING_UP.value
    assert pointer.mirror_x == DEFAULT_POINTER_MIRROR_X
    assert pointer.smoothing is SmoothingKind.EMA
    assert pointer.alpha == DEFAULT_POINTER_SMOOTHING_ALPHA
    assert pointer.active_zone == ActiveZoneConfig()


def test_app_config_uses_pointer_defaults() -> None:
    assert AppConfig().pointer == PointerConfig()


def test_pointer_parses_smoothing_kinds() -> None:
    assert PointerConfig.model_validate({"smoothing": "none"}).smoothing is SmoothingKind.NONE
    assert PointerConfig.model_validate({"smoothing": "ema"}).smoothing is SmoothingKind.EMA


@pytest.mark.parametrize(
    "zone",
    [
        {"x_min": 0.8, "x_max": 0.2},
        {"x_min": 0.5, "x_max": 0.5},
    ],
)
def test_active_zone_rejects_inverted_x_range(zone: dict[str, float]) -> None:
    with pytest.raises(ValidationError, match="x_min < x_max"):
        ActiveZoneConfig.model_validate(zone)


@pytest.mark.parametrize(
    "zone",
    [
        {"y_min": 0.9, "y_max": 0.1},
        {"y_min": 0.5, "y_max": 0.5},
    ],
)
def test_active_zone_rejects_inverted_y_range(zone: dict[str, float]) -> None:
    with pytest.raises(ValidationError, match="y_min < y_max"):
        ActiveZoneConfig.model_validate(zone)


@pytest.mark.parametrize("field", ["x_min", "x_max", "y_min", "y_max"])
@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_active_zone_rejects_out_of_range_coordinates(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        ActiveZoneConfig.model_validate({field: value})


@pytest.mark.parametrize("alpha", [0.0, -0.1, 1.1])
def test_pointer_rejects_alpha_out_of_range(alpha: float) -> None:
    with pytest.raises(ValidationError):
        PointerConfig.model_validate({"alpha": alpha})


def test_pointer_rejects_missing_activation_gesture() -> None:
    with pytest.raises(ValidationError):
        PointerConfig.model_validate({"activation_gesture": None})


def test_pointer_rejects_none_gesture() -> None:
    with pytest.raises(ValidationError, match="None no puede activar el puntero"):
        PointerConfig.model_validate({"activation_gesture": GESTURE_NONE.value})


def test_pointer_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PointerConfig.model_validate({"pointer": True})


def test_face_auth_min_password_length_default() -> None:
    assert FaceAuthConfig().min_password_length == DEFAULT_MIN_PASSWORD_LENGTH


def test_face_auth_rejects_invalid_min_password_length() -> None:
    with pytest.raises(ValidationError, match="min_password_length"):
        FaceAuthConfig(min_password_length=0)
