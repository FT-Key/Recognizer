"""Landmarks de manos detectadas."""

from dataclasses import dataclass
from enum import StrEnum

HAND_LANDMARK_COUNT = 21
WRIST_LANDMARK_INDEX = 0

# Topologia oficial del modelo de 21 landmarks de MediaPipe.
HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
)


class Handedness(StrEnum):
    """Lateralidad estimada por el modelo."""

    LEFT = "Left"
    RIGHT = "Right"
    UNKNOWN = "Unknown"


@dataclass(frozen=True, slots=True)
class Point:
    """Punto 3D normalizado respecto al fotograma."""

    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class HandLandmarks:
    """Una mano con su lateralidad, confianza y puntos normalizados."""

    handedness: Handedness
    confidence: float
    points: tuple[Point, ...]
