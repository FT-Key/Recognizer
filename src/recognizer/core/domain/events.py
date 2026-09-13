"""Eventos del dominio publicados a traves del bus."""

from dataclasses import dataclass

from recognizer.core.domain.gesture import GestureName
from recognizer.core.domain.hand import Handedness, HandLandmarks


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base de los eventos del dominio."""

    timestamp: float


@dataclass(frozen=True, slots=True)
class HandsDetected(DomainEvent):
    """Manos detectadas en un fotograma (puede ir vacio)."""

    hands: tuple[HandLandmarks, ...]


@dataclass(frozen=True, slots=True)
class GestureDetected(DomainEvent):
    """Gesto confirmado por el estabilizador para una mano."""

    gesture: GestureName
    confidence: float
    handedness: Handedness


@dataclass(frozen=True, slots=True)
class GestureReleased(DomainEvent):
    """Gesto confirmado que dejo de observarse en una mano."""

    gesture: GestureName
    handedness: Handedness


@dataclass(frozen=True, slots=True)
class PointerMoved(DomainEvent):
    """Posicion normalizada del puntero publicada mientras esta activo."""

    x: float
    y: float
