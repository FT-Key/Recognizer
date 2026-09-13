"""Gestos de mano del dominio."""

from dataclasses import dataclass
from enum import StrEnum

from recognizer.core.domain.hand import Handedness, HandLandmarks


class GestureName(StrEnum):
    """Gestos predefinidos del modelo GestureRecognizer."""

    NONE = "None"
    CLOSED_FIST = "Closed_Fist"
    OPEN_PALM = "Open_Palm"
    POINTING_UP = "Pointing_Up"
    THUMB_DOWN = "Thumb_Down"
    THUMB_UP = "Thumb_Up"
    VICTORY = "Victory"
    I_LOVE_YOU = "ILoveYou"


@dataclass(frozen=True, slots=True)
class DetectedGesture:
    """Gesto crudo de una mano, aun sin estabilizar."""

    name: GestureName
    confidence: float
    handedness: Handedness


@dataclass(frozen=True, slots=True)
class StableGesture:
    """Gesto confirmado tras varios fotogramas consecutivos observandolo."""

    name: GestureName
    confidence: float
    handedness: Handedness


@dataclass(frozen=True, slots=True)
class GestureRecognition:
    """Manos y gestos de una clasificacion, paralelos por indice.

    ``detections[i]`` corresponde a ``hands[i]``: hay una deteccion por mano
    y en el mismo orden.
    """

    hands: tuple[HandLandmarks, ...]
    detections: tuple[DetectedGesture, ...]
