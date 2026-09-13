"""Modelos de configuracion tipados y validados con pydantic."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from recognizer.core.constants import (
    DEFAULT_ACTION_COOLDOWN_SECONDS,
    DEFAULT_CAMERA_DEVICE_INDEX,
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    DEFAULT_GESTURE_MODEL_PATH,
    DEFAULT_HAND_MODEL_PATH,
    DEFAULT_MAX_HANDS,
    DEFAULT_MIN_DETECTION_CONFIDENCE,
    DEFAULT_MIN_GESTURE_CONFIDENCE,
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
from recognizer.core.domain.action import MediaKey
from recognizer.core.domain.gesture import GestureName
from recognizer.core.domain.pointer import SmoothingKind


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


class GestureConfig(BaseModel):
    """Parametros del clasificador de gestos y su estabilizador."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_path: str = Field(default=DEFAULT_GESTURE_MODEL_PATH, min_length=1)
    max_hands: int = Field(default=DEFAULT_MAX_HANDS, ge=1)
    min_detection_confidence: float = Field(default=DEFAULT_MIN_DETECTION_CONFIDENCE, ge=0, le=1)
    min_presence_confidence: float = Field(default=DEFAULT_MIN_PRESENCE_CONFIDENCE, ge=0, le=1)
    min_tracking_confidence: float = Field(default=DEFAULT_MIN_TRACKING_CONFIDENCE, ge=0, le=1)
    stabilization_frames: int = Field(default=DEFAULT_STABILIZATION_FRAMES, ge=1)
    release_frames: int = Field(default=DEFAULT_RELEASE_FRAMES, ge=1)
    min_gesture_confidence: float = Field(default=DEFAULT_MIN_GESTURE_CONFIDENCE, ge=0, le=1)


class MediaKeyActionConfig(BaseModel):
    """Accion que pulsa una tecla multimedia."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["media_key"] = "media_key"
    key: MediaKey


class HotkeyActionConfig(BaseModel):
    """Accion que pulsa una combinacion de teclas."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["hotkey"] = "hotkey"
    keys: tuple[str, ...] = Field(min_length=1)


class CommandActionConfig(BaseModel):
    """Accion que lanza un comando local."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["command"] = "command"
    argv: tuple[str, ...] = Field(min_length=1)


ActionConfig = Annotated[
    MediaKeyActionConfig | HotkeyActionConfig | CommandActionConfig,
    Field(discriminator="type"),
]


class ActionsConfig(BaseModel):
    """Acciones locales y su mapeo por gesto confirmado."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cooldown_seconds: float = Field(default=DEFAULT_ACTION_COOLDOWN_SECONDS, ge=0)
    mappings: dict[GestureName, ActionConfig] = Field(default_factory=dict)

    @field_validator("mappings")
    @classmethod
    def _reject_none_gesture(
        cls,
        mappings: dict[GestureName, ActionConfig],
    ) -> dict[GestureName, ActionConfig]:
        if GestureName.NONE in mappings:
            msg = "El gesto None no puede mapearse a una accion."
            raise ValueError(msg)
        return mappings


class ActiveZoneConfig(BaseModel):
    """Zona activa del fotograma que se proyecta sobre toda la pantalla."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x_min: float = Field(default=DEFAULT_POINTER_ACTIVE_ZONE_MIN, ge=0, le=1)
    x_max: float = Field(default=DEFAULT_POINTER_ACTIVE_ZONE_MAX, ge=0, le=1)
    y_min: float = Field(default=DEFAULT_POINTER_ACTIVE_ZONE_MIN, ge=0, le=1)
    y_max: float = Field(default=DEFAULT_POINTER_ACTIVE_ZONE_MAX, ge=0, le=1)

    @model_validator(mode="after")
    def _validate_ranges(self) -> Self:
        if self.x_min >= self.x_max:
            msg = "La zona activa requiere x_min < x_max."
            raise ValueError(msg)
        if self.y_min >= self.y_max:
            msg = "La zona activa requiere y_min < y_max."
            raise ValueError(msg)
        return self


class PointerConfig(BaseModel):
    """Puntero virtual: activacion, calibracion y suavizado."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = DEFAULT_POINTER_ENABLED
    activation_gesture: GestureName = GestureName.POINTING_UP
    mirror_x: bool = DEFAULT_POINTER_MIRROR_X
    smoothing: SmoothingKind = SmoothingKind.EMA
    alpha: float = Field(default=DEFAULT_POINTER_SMOOTHING_ALPHA, gt=0, le=1)
    active_zone: ActiveZoneConfig = Field(default_factory=ActiveZoneConfig)

    @field_validator("activation_gesture")
    @classmethod
    def _reject_none_gesture(cls, gesture: GestureName) -> GestureName:
        if gesture is GestureName.NONE:
            msg = "El gesto None no puede activar el puntero."
            raise ValueError(msg)
        return gesture


class AppConfig(BaseModel):
    """Configuracion raiz de la aplicacion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    camera: CameraConfig = Field(default_factory=CameraConfig)
    hands: HandsConfig = Field(default_factory=HandsConfig)
    gestures: GestureConfig = Field(default_factory=GestureConfig)
    pointer: PointerConfig = Field(default_factory=PointerConfig)
    actions: ActionsConfig = Field(default_factory=ActionsConfig)
