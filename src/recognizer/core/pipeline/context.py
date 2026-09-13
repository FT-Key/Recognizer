"""Contexto que fluye a traves del pipeline."""

from dataclasses import dataclass

from recognizer.core.domain.frame import Frame
from recognizer.core.domain.hand import HandLandmarks


@dataclass(frozen=True, slots=True)
class FrameContext:
    """Fotograma y resultados que los processors van acumulando."""

    frame: Frame
    hands: tuple[HandLandmarks, ...] = ()
