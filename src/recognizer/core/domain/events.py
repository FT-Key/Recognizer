"""Eventos del dominio publicados a traves del bus."""

from dataclasses import dataclass

from recognizer.core.domain.hand import HandLandmarks


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base de los eventos del dominio."""

    timestamp: float


@dataclass(frozen=True, slots=True)
class HandsDetected(DomainEvent):
    """Manos detectadas en un fotograma (puede ir vacio)."""

    hands: tuple[HandLandmarks, ...]
