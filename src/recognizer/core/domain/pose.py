"""Postura corporal estimada: puntos clave normalizados (dominio puro).

Un ``Pose`` es el conjunto de ``Keypoint`` que un estimador de pose (YOLO pose
hoy) devuelve para una persona. Las coordenadas son normalizadas (0..1) respecto
al fotograma y el eje Y crece hacia abajo, igual que el resto del dominio.
"""

from dataclasses import dataclass
from enum import StrEnum

from recognizer.core.domain.detection import (
    MAX_CONFIDENCE,
    MAX_NORMALIZED_COORDINATE,
    MIN_CONFIDENCE,
    MIN_NORMALIZED_COORDINATE,
)
from recognizer.core.errors import ConfigError


class PoseKeypoint(StrEnum):
    """Puntos clave del esqueleto (orden COCO de 17 puntos de YOLO pose)."""

    NOSE = "nose"
    LEFT_EYE = "left_eye"
    RIGHT_EYE = "right_eye"
    LEFT_EAR = "left_ear"
    RIGHT_EAR = "right_ear"
    LEFT_SHOULDER = "left_shoulder"
    RIGHT_SHOULDER = "right_shoulder"
    LEFT_ELBOW = "left_elbow"
    RIGHT_ELBOW = "right_elbow"
    LEFT_WRIST = "left_wrist"
    RIGHT_WRIST = "right_wrist"
    LEFT_HIP = "left_hip"
    RIGHT_HIP = "right_hip"
    LEFT_KNEE = "left_knee"
    RIGHT_KNEE = "right_knee"
    LEFT_ANKLE = "left_ankle"
    RIGHT_ANKLE = "right_ankle"


# Orden canonico del modelo: el indice de la lista es el del tensor de keypoints.
COCO_KEYPOINT_ORDER: tuple[PoseKeypoint, ...] = (
    PoseKeypoint.NOSE,
    PoseKeypoint.LEFT_EYE,
    PoseKeypoint.RIGHT_EYE,
    PoseKeypoint.LEFT_EAR,
    PoseKeypoint.RIGHT_EAR,
    PoseKeypoint.LEFT_SHOULDER,
    PoseKeypoint.RIGHT_SHOULDER,
    PoseKeypoint.LEFT_ELBOW,
    PoseKeypoint.RIGHT_ELBOW,
    PoseKeypoint.LEFT_WRIST,
    PoseKeypoint.RIGHT_WRIST,
    PoseKeypoint.LEFT_HIP,
    PoseKeypoint.RIGHT_HIP,
    PoseKeypoint.LEFT_KNEE,
    PoseKeypoint.RIGHT_KNEE,
    PoseKeypoint.LEFT_ANKLE,
    PoseKeypoint.RIGHT_ANKLE,
)


@dataclass(frozen=True, slots=True)
class Keypoint:
    """Un punto clave: nombre, posicion normalizada (0..1) y confianza."""

    name: PoseKeypoint
    x: float
    y: float
    confidence: float

    def __post_init__(self) -> None:
        for axis, value in (("x", self.x), ("y", self.y)):
            if not MIN_NORMALIZED_COORDINATE <= value <= MAX_NORMALIZED_COORDINATE:
                msg = f"El keypoint requiere 0 <= {axis} <= 1 (llego {value})."
                raise ConfigError(msg)
        if not MIN_CONFIDENCE <= self.confidence <= MAX_CONFIDENCE:
            msg = f"La confianza requiere 0 <= confidence <= 1 (llego {self.confidence})."
            raise ConfigError(msg)


@dataclass(frozen=True, slots=True)
class Pose:
    """Postura de una persona: confianza global y sus puntos clave."""

    confidence: float
    keypoints: tuple[Keypoint, ...] = ()

    def __post_init__(self) -> None:
        if not MIN_CONFIDENCE <= self.confidence <= MAX_CONFIDENCE:
            msg = f"La confianza requiere 0 <= confidence <= 1 (llego {self.confidence})."
            raise ConfigError(msg)

    def keypoint(self, name: PoseKeypoint) -> Keypoint | None:
        """Devuelve el punto clave con ese nombre o ``None`` si no esta."""
        for keypoint in self.keypoints:
            if keypoint.name is name:
                return keypoint
        return None
