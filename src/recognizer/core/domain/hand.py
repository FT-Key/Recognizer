"""Landmarks de manos detectadas."""

from dataclasses import dataclass
from enum import StrEnum

HAND_LANDMARK_COUNT = 21
WRIST_LANDMARK_INDEX = 0

# Topologia oficial del modelo de 21 landmarks de MediaPipe: CMC/MCP/IP/PIP/DIP/TIP.
THUMB_CMC_LANDMARK_INDEX = 1
THUMB_MCP_LANDMARK_INDEX = 2
THUMB_IP_LANDMARK_INDEX = 3
THUMB_TIP_LANDMARK_INDEX = 4

INDEX_FINGER_MCP_LANDMARK_INDEX = 5
INDEX_FINGER_PIP_LANDMARK_INDEX = 6
INDEX_FINGER_DIP_LANDMARK_INDEX = 7
INDEX_FINGER_TIP_LANDMARK_INDEX = 8

MIDDLE_FINGER_MCP_LANDMARK_INDEX = 9
MIDDLE_FINGER_PIP_LANDMARK_INDEX = 10
MIDDLE_FINGER_DIP_LANDMARK_INDEX = 11
MIDDLE_FINGER_TIP_LANDMARK_INDEX = 12

RING_FINGER_MCP_LANDMARK_INDEX = 13
RING_FINGER_PIP_LANDMARK_INDEX = 14
RING_FINGER_DIP_LANDMARK_INDEX = 15
RING_FINGER_TIP_LANDMARK_INDEX = 16

PINKY_MCP_LANDMARK_INDEX = 17
PINKY_PIP_LANDMARK_INDEX = 18
PINKY_DIP_LANDMARK_INDEX = 19
PINKY_TIP_LANDMARK_INDEX = 20

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


_HAND_SWAP: dict[Handedness, Handedness] = {
    Handedness.LEFT: Handedness.RIGHT,
    Handedness.RIGHT: Handedness.LEFT,
    Handedness.UNKNOWN: Handedness.UNKNOWN,
}


def other_hand(hand: Handedness) -> Handedness:
    """Devuelve la lateralidad contraria; ``UNKNOWN`` se conserva."""
    return _HAND_SWAP[hand]


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
