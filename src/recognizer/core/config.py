"""Modelos de configuracion tipados y validados con pydantic."""

from pydantic import BaseModel, ConfigDict, Field

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


class CameraConfig(BaseModel):
    """Parametros de la camara local."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    device_index: int = Field(default=DEFAULT_CAMERA_DEVICE_INDEX, ge=0)
    width: int = Field(default=DEFAULT_FRAME_WIDTH, gt=0)
    height: int = Field(default=DEFAULT_FRAME_HEIGHT, gt=0)
    target_fps: int = Field(default=DEFAULT_TARGET_FPS, gt=0)


class HandsConfig(BaseModel):
    """Parametros del detector de manos."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_path: str = Field(default=DEFAULT_HAND_MODEL_PATH, min_length=1)
    max_hands: int = Field(default=DEFAULT_MAX_HANDS, ge=1)
    min_detection_confidence: float = Field(default=DEFAULT_MIN_DETECTION_CONFIDENCE, ge=0, le=1)
    min_presence_confidence: float = Field(default=DEFAULT_MIN_PRESENCE_CONFIDENCE, ge=0, le=1)
    min_tracking_confidence: float = Field(default=DEFAULT_MIN_TRACKING_CONFIDENCE, ge=0, le=1)


class AppConfig(BaseModel):
    """Configuracion raiz de la aplicacion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    camera: CameraConfig = Field(default_factory=CameraConfig)
    hands: HandsConfig = Field(default_factory=HandsConfig)
