"""Contexto que fluye a traves del pipeline."""

from dataclasses import dataclass

from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import DetectedGesture, StableGesture
from recognizer.core.domain.hand import HandLandmarks
from recognizer.core.domain.pointer import PointerPosition


@dataclass(frozen=True, slots=True)
class FrameContext:
    """Fotograma y resultados que los processors van acumulando."""

    frame: Frame
    hands: tuple[HandLandmarks, ...] = ()
    detections: tuple[DetectedGesture, ...] = ()
    gestures: tuple[StableGesture, ...] = ()
    pointer: PointerPosition | None = None
