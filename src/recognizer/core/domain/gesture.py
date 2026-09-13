"""Gestos de mano del dominio.

``GestureId`` es un value object abierto: cualquier etiqueta valida puede ser un
gesto (predefinido, personalizado o declarado por una regla). El catalogo
``GestureCatalog`` resuelve etiquetas a identificadores y valida colisiones.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from recognizer.core.domain.hand import Handedness, HandLandmarks
from recognizer.core.errors import ConfigError


@dataclass(frozen=True, slots=True)
class GestureId:
    """Identificador de gesto: etiqueta estable y sin espacios sobrantes."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or self.value != self.value.strip():
            msg = f"El identificador de gesto no es valido: {self.value!r}"
            raise ConfigError(msg)

    def __str__(self) -> str:
        """Devuelve la etiqueta del gesto."""
        return self.value


GESTURE_NONE = GestureId("None")
GESTURE_CLOSED_FIST = GestureId("Closed_Fist")
GESTURE_OPEN_PALM = GestureId("Open_Palm")
GESTURE_POINTING_UP = GestureId("Pointing_Up")
GESTURE_THUMB_DOWN = GestureId("Thumb_Down")
GESTURE_THUMB_UP = GestureId("Thumb_Up")
GESTURE_VICTORY = GestureId("Victory")
GESTURE_ILOVE_YOU = GestureId("ILoveYou")

CANNED_GESTURES: tuple[GestureId, ...] = (
    GESTURE_CLOSED_FIST,
    GESTURE_OPEN_PALM,
    GESTURE_POINTING_UP,
    GESTURE_THUMB_DOWN,
    GESTURE_THUMB_UP,
    GESTURE_VICTORY,
    GESTURE_ILOVE_YOU,
)

CANNED_GESTURE_LABELS: frozenset[str] = frozenset(gesture.value for gesture in CANNED_GESTURES)


class Finger(StrEnum):
    """Dedos de la mano usados por las reglas de gestos."""

    THUMB = "thumb"
    INDEX = "index"
    MIDDLE = "middle"
    RING = "ring"
    PINKY = "pinky"


class Direction8(StrEnum):
    """Direcciones de ocho sentidos para una condicion de regla."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    UP_LEFT = "up_left"
    UP_RIGHT = "up_right"
    DOWN_LEFT = "down_left"
    DOWN_RIGHT = "down_right"


class RulesPriority(StrEnum):
    """Orden de resolucion entre reglas y modelo."""

    RULES_FIRST = "rules_first"
    MODEL_FIRST = "model_first"


@dataclass(frozen=True, slots=True)
class GestureCatalog:
    """Gestos conocidos y resolucion de etiquetas a ``GestureId``."""

    known: frozenset[GestureId]
    labels: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.labels:
            object.__setattr__(
                self,
                "labels",
                frozenset(gesture.value for gesture in self.known),
            )

    def is_known(self, gesture: GestureId) -> bool:
        """Indica si el gesto pertenece al catalogo."""
        return gesture in self.known

    def resolve(self, label: str) -> GestureId | None:
        """Resuelve una etiqueta conocida; devuelve ``None`` si no existe."""
        if label not in self.labels:
            return None
        return GestureId(label)

    def require(self, label: str) -> GestureId:
        """Resuelve una etiqueta conocida o falla con ``ConfigError``."""
        gesture = self.resolve(label)
        if gesture is None:
            msg = f"Gesto desconocido en la configuracion: {label}"
            raise ConfigError(msg)
        return gesture

    @classmethod
    def from_labels(
        cls,
        *,
        custom_labels: Sequence[str],
        rule_names: Sequence[str],
    ) -> Self:
        """Construye el catalogo con predefinidos, personalizados y reglas.

        Raises:
            ConfigError: si una etiqueta colisiona con un gesto predefinido o
                se llama ``None``.
        """
        known = set(CANNED_GESTURES)
        labels = set(CANNED_GESTURE_LABELS)
        for label in (*custom_labels, *rule_names):
            if label in CANNED_GESTURE_LABELS or label == GESTURE_NONE.value:
                msg = f"El gesto {label!r} colisiona con un gesto predefinido."
                raise ConfigError(msg)
            known.add(GestureId(label))
            labels.add(label)
        return cls(known=frozenset(known), labels=frozenset(labels))


@dataclass(frozen=True, slots=True)
class DetectedGesture:
    """Gesto crudo de una mano, aun sin estabilizar."""

    name: GestureId
    confidence: float
    handedness: Handedness


@dataclass(frozen=True, slots=True)
class StableGesture:
    """Gesto confirmado tras varios fotogramas consecutivos observandolo."""

    name: GestureId
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
